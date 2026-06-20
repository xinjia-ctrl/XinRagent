import asyncio
import json
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
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
    backend_message_id: str | None = None


TaskHandler = Callable[[TaskMessage], Awaitable[None]]


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

    async def run_worker(self, handlers: dict[str, TaskHandler], stop_event: asyncio.Event) -> None: ...


class InMemoryTaskQueue:
    def __init__(self) -> None:
        self._queue: asyncio.Queue[TaskMessage] = asyncio.Queue()

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

    async def run_worker(self, handlers: dict[str, TaskHandler], stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            task = await self.reserve(timeout_seconds=0.2)
            if task is None:
                continue
            await _dispatch_task(task, handlers)
            await self.ack(task)


class RedisStreamTaskQueue:
    def __init__(self, redis_url: str, key_prefix: str, stream_name: str = "default") -> None:
        self._client = redis.from_url(redis_url, decode_responses=True)
        self._stream_key = f"{key_prefix}:{stream_name}:stream"
        self._last_id = "0-0"

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

    async def run_worker(self, handlers: dict[str, TaskHandler], stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            task = await self.reserve(timeout_seconds=0.5)
            if task is None:
                continue
            await _dispatch_task(task, handlers)
            await self.ack(task)


class RocketMQTaskQueue:
    def __init__(
        self,
        name_server: str,
        producer_group: str,
        topic: str,
        consumer_group: str | None = None,
    ) -> None:
        self.name_server = name_server
        self.producer_group = producer_group
        self.consumer_group = consumer_group or f"{producer_group}-consumer"
        self.topic = topic
        self._producer = None

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
        )
        await asyncio.to_thread(self._send, task)
        return task

    async def reserve(self, timeout_seconds: float = 1.0) -> TaskMessage | None:
        await asyncio.sleep(timeout_seconds)
        return None

    async def ack(self, task: TaskMessage) -> None:
        return None

    async def run_worker(self, handlers: dict[str, TaskHandler], stop_event: asyncio.Event) -> None:
        client = _rocketmq_client()
        loop = asyncio.get_running_loop()
        consumer = client.PushConsumer(self.consumer_group)
        consumer.set_name_server_address(self.name_server)

        def consume(message):
            task = _task_from_json(message.body.decode("utf-8"))
            future = asyncio.run_coroutine_threadsafe(_dispatch_task(task, handlers), loop)
            future.result()
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
        producer.send_sync(message)

    def _get_producer(self, client):
        if self._producer is not None:
            return self._producer
        producer = client.Producer(self.producer_group)
        producer.set_name_server_address(self.name_server)
        producer.start()
        self._producer = producer
        return producer


async def _dispatch_task(task: TaskMessage, handlers: dict[str, TaskHandler]) -> None:
    handler = handlers.get(task.name)
    if handler is None:
        raise KeyError(f"未注册任务处理器: {task.name}")
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


def _task_from_json(value: str, backend_message_id: str | None = None) -> TaskMessage:
    payload = json.loads(value)
    return TaskMessage(
        task_id=payload["task_id"],
        name=payload["name"],
        payload=payload.get("payload") or {},
        idempotency_key=payload.get("idempotency_key"),
        context=payload.get("context") or {},
        created_at=float(payload.get("created_at") or time()),
        backend_message_id=backend_message_id,
    )


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
