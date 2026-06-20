import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field, replace
from time import time
from typing import Any, Protocol
from uuid import uuid4

import redis.asyncio as redis

from app.core.context import get_request_context
from app.core.exceptions import RagentException


@dataclass(frozen=True)
class TaskMessage:
    task_id: str
    name: str
    payload: dict[str, Any] = field(default_factory=dict)
    idempotency_key: str | None = None
    context: dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time)
    trace_id: str | None = None
    attempt: int = 0
    backend_message_id: str | None = None


TaskHandler = Callable[[TaskMessage], Awaitable[None]]


class TaskIdempotencyStore(Protocol):
    async def acquire(self, key: str, ttl_seconds: int) -> bool: ...

    async def release(self, key: str) -> None: ...


@dataclass(frozen=True)
class DeadLetterTask:
    task: TaskMessage
    error: str
    failed_at: float = field(default_factory=time)


@dataclass(frozen=True)
class TaskConsumeTrace:
    task_id: str
    name: str
    backend: str
    status: str
    attempt: int
    trace_id: str
    consumer_group: str | None = None
    error: str | None = None
    started_at: float = field(default_factory=time)
    ended_at: float | None = None


class TaskQueue(Protocol):
    async def enqueue(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> TaskMessage: ...

    async def reserve(self, timeout_seconds: float = 1.0) -> TaskMessage | None: ...

    async def ack(self, task: TaskMessage) -> None: ...

    async def run_worker(
        self,
        handlers: dict[str, TaskHandler],
        stop_event: asyncio.Event,
        *,
        idempotency_store: TaskIdempotencyStore | None = None,
        idempotency_ttl_seconds: int = 3600,
        max_attempts: int = 3,
    ) -> None: ...


class InMemoryTaskQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[TaskMessage] = asyncio.Queue()
        self.dead_letters: list[DeadLetterTask] = []
        self.consume_traces: list[TaskConsumeTrace] = []

    async def enqueue(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> TaskMessage:
        task = TaskMessage(
            task_id=task_id or uuid4().hex,
            name=name,
            payload=payload,
            idempotency_key=idempotency_key,
            context=_current_context_payload(),
            trace_id=_current_trace_id(),
        )
        await self._queue.put(task)
        return task

    async def reserve(self, timeout_seconds: float = 1.0) -> TaskMessage | None:
        try:
            return await asyncio.wait_for(self._queue.get(), timeout_seconds)
        except TimeoutError:
            return None

    async def ack(self, task: TaskMessage) -> None:
        self._queue.task_done()

    async def run_worker(
        self,
        handlers: dict[str, TaskHandler],
        stop_event: asyncio.Event,
        *,
        idempotency_store: TaskIdempotencyStore | None = None,
        idempotency_ttl_seconds: int = 3600,
        max_attempts: int = 3,
    ) -> None:
        while not stop_event.is_set():
            task = await self.reserve(timeout_seconds=0.2)
            if task is None:
                continue
            try:
                await _dispatch_task(
                    task,
                    handlers,
                    idempotency_store=idempotency_store,
                    idempotency_ttl_seconds=idempotency_ttl_seconds,
                )
                self.consume_traces.append(_consume_trace(task, backend="memory", status="success"))
            except Exception as exc:
                if _should_retry(task, max_attempts):
                    await self._queue.put(replace(task, attempt=task.attempt + 1))
                    self.consume_traces.append(
                        _consume_trace(task, backend="memory", status="retry", error=str(exc)),
                    )
                else:
                    self.dead_letters.append(DeadLetterTask(task=task, error=str(exc)))
                    self.consume_traces.append(
                        _consume_trace(task, backend="memory", status="dead_letter", error=str(exc)),
                    )
            await self.ack(task)


class RedisStreamTaskQueue:
    def __init__(self, redis_url: str, key_prefix: str, stream_name: str = "default") -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._stream_key = f"{key_prefix}:{stream_name}:stream"
        self._dlq_key = f"{key_prefix}:{stream_name}:dlq"
        self._last_id = "0-0"
        self.consume_traces: list[TaskConsumeTrace] = []

    async def enqueue(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> TaskMessage:
        task = TaskMessage(
            task_id=task_id or uuid4().hex,
            name=name,
            payload=payload,
            idempotency_key=idempotency_key,
            context=_current_context_payload(),
            trace_id=_current_trace_id(),
        )
        await self._client.xadd(self._stream_key, {"task": json.dumps(asdict(task), ensure_ascii=False)})
        return task

    async def reserve(self, timeout_seconds: float = 1.0) -> TaskMessage | None:
        response = await self._client.xread(
            {self._stream_key: self._last_id},
            count=1,
            block=max(int(timeout_seconds * 1000), 1),
        )
        if not response:
            return None
        _, messages = response[0]
        message_id, fields = messages[0]
        self._last_id = message_id
        return _task_from_json(fields["task"], backend_message_id=message_id)

    async def ack(self, task: TaskMessage) -> None:
        if task.backend_message_id:
            await self._client.xdel(self._stream_key, task.backend_message_id)

    async def run_worker(
        self,
        handlers: dict[str, TaskHandler],
        stop_event: asyncio.Event,
        *,
        idempotency_store: TaskIdempotencyStore | None = None,
        idempotency_ttl_seconds: int = 3600,
        max_attempts: int = 3,
    ) -> None:
        while not stop_event.is_set():
            task = await self.reserve(timeout_seconds=0.5)
            if task is None:
                continue
            try:
                await _dispatch_task(
                    task,
                    handlers,
                    idempotency_store=idempotency_store,
                    idempotency_ttl_seconds=idempotency_ttl_seconds,
                )
                self.consume_traces.append(_consume_trace(task, backend="redis", status="success"))
            except Exception as exc:
                if _should_retry(task, max_attempts):
                    await self._client.xadd(
                        self._stream_key,
                        {"task": json.dumps(asdict(replace(task, attempt=task.attempt + 1)), ensure_ascii=False)},
                    )
                    self.consume_traces.append(
                        _consume_trace(task, backend="redis", status="retry", error=str(exc)),
                    )
                else:
                    await self._client.xadd(
                        self._dlq_key,
                        {"task": json.dumps(asdict(task), ensure_ascii=False), "error": str(exc)},
                    )
                    self.consume_traces.append(
                        _consume_trace(task, backend="redis", status="dead_letter", error=str(exc)),
                    )
            await self.ack(task)


class RocketMQTaskQueue:
    def __init__(
        self,
        name_server: str,
        producer_group: str,
        topic: str,
        consumer_group: str | None = None,
        dlq_topic: str | None = None,
        max_attempts: int = 3,
    ) -> None:
        self.name_server = name_server
        self.producer_group = producer_group
        self.consumer_group = consumer_group or f"{producer_group}-consumer"
        self.topic = topic
        self.dlq_topic = dlq_topic or f"{topic}.DLQ"
        self.max_attempts = max_attempts
        self._producer = None
        self.dead_letters: list[DeadLetterTask] = []
        self.consume_traces: list[TaskConsumeTrace] = []

    async def enqueue(
        self,
        name: str,
        payload: dict[str, Any],
        *,
        task_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> TaskMessage:
        task = TaskMessage(
            task_id=task_id or uuid4().hex,
            name=name,
            payload=payload,
            idempotency_key=idempotency_key,
            context=_current_context_payload(),
            trace_id=_current_trace_id(),
        )
        await asyncio.to_thread(self._send, task)
        return task

    async def reserve(self, timeout_seconds: float = 1.0) -> TaskMessage | None:
        await asyncio.sleep(timeout_seconds)
        return None

    async def ack(self, task: TaskMessage) -> None:
        return None

    async def run_worker(
        self,
        handlers: dict[str, TaskHandler],
        stop_event: asyncio.Event,
        *,
        idempotency_store: TaskIdempotencyStore | None = None,
        idempotency_ttl_seconds: int = 3600,
        max_attempts: int | None = None,
    ) -> None:
        client = _rocketmq_client()
        loop = asyncio.get_running_loop()
        consumer = client.PushConsumer(self.consumer_group)
        consumer.set_name_server_address(self.name_server)
        retry_limit = max_attempts or self.max_attempts

        def consume(message):
            task = _task_from_json(_message_body(message).decode("utf-8"), backend_message_id=_message_id(message))
            reconsume_times = _message_reconsume_times(message)
            if reconsume_times > task.attempt:
                task = replace(task, attempt=reconsume_times)
            future = asyncio.run_coroutine_threadsafe(
                _dispatch_task(
                    task,
                    handlers,
                    idempotency_store=idempotency_store,
                    idempotency_ttl_seconds=idempotency_ttl_seconds,
                ),
                loop,
            )
            try:
                future.result()
                self.consume_traces.append(
                    _consume_trace(
                        task,
                        backend="rocketmq",
                        status="success",
                        consumer_group=self.consumer_group,
                    ),
                )
            except Exception as exc:
                if _should_retry(task, retry_limit):
                    self.consume_traces.append(
                        _consume_trace(
                            task,
                            backend="rocketmq",
                            status="retry",
                            consumer_group=self.consumer_group,
                            error=str(exc),
                        ),
                    )
                    return _rocketmq_reconsume_later(client)
                self.dead_letters.append(DeadLetterTask(task=task, error=str(exc)))
                self._send_dead_letter(task, str(exc))
                self.consume_traces.append(
                    _consume_trace(
                        task,
                        backend="rocketmq",
                        status="dead_letter",
                        consumer_group=self.consumer_group,
                        error=str(exc),
                    ),
                )
            return client.ConsumeStatus.CONSUME_SUCCESS

        consumer.subscribe(self.topic, "*", consume)
        consumer.start()
        try:
            while not stop_event.is_set():
                await asyncio.sleep(0.2)
        finally:
            consumer.shutdown()

    def _send(self, task: TaskMessage) -> None:
        client = _rocketmq_client()
        producer = self._get_producer(client)
        message = client.Message(self.topic)
        message.set_tags(task.name)
        message.set_keys(task.idempotency_key or task.task_id)
        message.set_body(json.dumps(asdict(task), ensure_ascii=False).encode("utf-8"))
        _set_message_property(message, "TRACE_ID", task.trace_id or task.task_id)
        _set_message_property(message, "TASK_ID", task.task_id)
        producer.send_sync(message)

    def _send_dead_letter(self, task: TaskMessage, error: str) -> None:
        client = _rocketmq_client()
        producer = self._get_producer(client)
        message = client.Message(self.dlq_topic)
        message.set_tags("DLQ")
        message.set_keys(task.idempotency_key or task.task_id)
        message.set_body(
            json.dumps(
                {
                    "task": asdict(task),
                    "error": error,
                    "failed_at": time(),
                    "consumer_group": self.consumer_group,
                },
                ensure_ascii=False,
            ).encode("utf-8"),
        )
        _set_message_property(message, "TRACE_ID", task.trace_id or task.task_id)
        _set_message_property(message, "TASK_ID", task.task_id)
        _set_message_property(message, "CONSUMER_GROUP", self.consumer_group)
        producer.send_sync(message)

    def _get_producer(self, client):
        if self._producer is not None:
            return self._producer
        producer = client.Producer(self.producer_group)
        producer.set_name_server_address(self.name_server)
        producer.start()
        self._producer = producer
        return producer


async def _dispatch_task(
    task: TaskMessage,
    handlers: dict[str, TaskHandler],
    *,
    idempotency_store: TaskIdempotencyStore | None = None,
    idempotency_ttl_seconds: int = 3600,
) -> None:
    handler = handlers.get(task.name)
    if handler is None:
        raise KeyError(f"未注册任务处理器: {task.name}")
    if idempotency_store is not None and task.idempotency_key:
        acquired = await idempotency_store.acquire(task.idempotency_key, idempotency_ttl_seconds)
        if not acquired:
            return
        try:
            await handler(task)
        except Exception:
            await idempotency_store.release(task.idempotency_key)
            raise
        return
    await handler(task)


def _current_context_payload() -> dict[str, Any]:
    context = get_request_context()
    if context is None:
        return {}
    return {
        "requestId": context.request_id,
        "userId": context.user_id,
        "expiresAt": context.expires_at,
    }


def _current_trace_id() -> str:
    context = get_request_context()
    if context is None:
        return uuid4().hex
    return context.request_id


def _task_from_json(value: str, backend_message_id: str | None = None) -> TaskMessage:
    payload = json.loads(value)
    return TaskMessage(
        task_id=payload["task_id"],
        name=payload["name"],
        payload=payload.get("payload") or {},
        idempotency_key=payload.get("idempotency_key"),
        context=payload.get("context") or {},
        created_at=float(payload.get("created_at") or time()),
        trace_id=payload.get("trace_id"),
        attempt=int(payload.get("attempt") or 0),
        backend_message_id=backend_message_id,
    )


def _should_retry(task: TaskMessage, max_attempts: int) -> bool:
    return task.attempt + 1 < max_attempts


def _consume_trace(
    task: TaskMessage,
    *,
    backend: str,
    status: str,
    consumer_group: str | None = None,
    error: str | None = None,
) -> TaskConsumeTrace:
    now = time()
    return TaskConsumeTrace(
        task_id=task.task_id,
        name=task.name,
        backend=backend,
        status=status,
        attempt=task.attempt,
        trace_id=task.trace_id or task.task_id,
        consumer_group=consumer_group,
        error=error,
        started_at=now,
        ended_at=now,
    )


def _message_id(message: Any) -> str | None:
    for attr in ("id", "msg_id", "message_id", "get_msg_id"):
        value = getattr(message, attr, None)
        if value:
            return str(value() if callable(value) else value)
    return None


def _message_body(message: Any) -> bytes:
    value = getattr(message, "body", b"")
    if callable(value):
        value = value()
    return value if isinstance(value, bytes) else str(value).encode("utf-8")


def _message_reconsume_times(message: Any) -> int:
    value = 0
    for attr in ("reconsume_times", "get_reconsume_times"):
        value = getattr(message, attr, None)
        if value is not None:
            value = value() if callable(value) else value
            break
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _rocketmq_reconsume_later(client):
    consume_status = client.ConsumeStatus
    return getattr(consume_status, "RECONSUME_LATER", consume_status.CONSUME_SUCCESS)


def _set_message_property(message: Any, key: str, value: str) -> None:
    setter = getattr(message, "set_property", None)
    if callable(setter):
        setter(key, value)


def _rocketmq_client():
    try:
        from rocketmq import client
    except ImportError as exc:
        raise RagentException(
            message="RocketMQ SDK 未安装，请安装 rocketmq-client-python 或切换 RAG_TASK_QUEUE_BACKEND",
            code="ROCKETMQ_CLIENT_MISSING",
            status_code=500,
        ) from exc
    return client
