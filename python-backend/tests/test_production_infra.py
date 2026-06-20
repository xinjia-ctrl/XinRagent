import asyncio
import json
import threading
from dataclasses import asdict
from time import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.context import RequestContext, get_request_context, reset_request_context, set_request_context
from app.core.exceptions import RagentException
from app.infra import (
    InMemoryIdempotencyStore,
    InMemoryTaskQueue,
    InMemoryUploadRateLimiter,
    TaskMessage,
    TransactionalTaskPublisher,
    WorkerThreadPool,
)
from app.infra.task_queue import RocketMQTaskQueue


@pytest.mark.asyncio
async def test_in_memory_task_queue_captures_ttl_request_context() -> None:
    queue = InMemoryTaskQueue()
    token = set_request_context(
        RequestContext(request_id="req-1", user_id="user-1", expires_at=time() + 30),
    )
    try:
        await queue.enqueue("demo.task", {"value": 1}, idempotency_key="idem-1")
    finally:
        reset_request_context(token)

    task = await queue.reserve()

    assert task is not None
    assert task.name == "demo.task"
    assert task.idempotency_key == "idem-1"
    assert task.context["requestId"] == "req-1"


@pytest.mark.asyncio
async def test_in_memory_idempotency_store_rejects_duplicate_key() -> None:
    store = InMemoryIdempotencyStore()

    assert await store.acquire("same-key", ttl_seconds=60) is True
    assert await store.acquire("same-key", ttl_seconds=60) is False
    await store.release("same-key")
    assert await store.acquire("same-key", ttl_seconds=60) is True


@pytest.mark.asyncio
async def test_in_memory_task_queue_retries_then_dead_letters_failure() -> None:
    queue = InMemoryTaskQueue()
    stop_event = asyncio.Event()
    attempts: list[int] = []

    async def handler(task: TaskMessage) -> None:
        attempts.append(task.attempt)
        if task.attempt >= 1:
            stop_event.set()
        raise RuntimeError("boom")

    await queue.enqueue("demo.task", {"value": 1}, task_id="task-1")
    await queue.run_worker({"demo.task": handler}, stop_event, max_attempts=2)

    assert attempts == [0, 1]
    assert queue.dead_letters[0].task.task_id == "task-1"
    assert [trace.status for trace in queue.consume_traces] == ["retry", "dead_letter"]


@pytest.mark.asyncio
async def test_upload_rate_limiter_raises_429_when_limit_exceeded() -> None:
    limiter = InMemoryUploadRateLimiter(limit_per_minute=1)

    await limiter.check("user-1")
    with pytest.raises(RagentException) as exc_info:
        await limiter.check("user-1")

    assert exc_info.value.status_code == 429
    assert exc_info.value.code == "UPLOAD_RATE_LIMITED"


@pytest.mark.asyncio
async def test_worker_thread_pool_runs_blocking_function() -> None:
    pool = WorkerThreadPool(max_workers=1)
    try:
        result = await pool.run_blocking(lambda left, right: left + right, 2, 3)
    finally:
        pool.shutdown()

    assert result == 5


def test_request_context_expires_after_ttl() -> None:
    token = set_request_context(RequestContext(request_id="expired", expires_at=time() - 1))
    try:
        assert get_request_context() is None
    finally:
        reset_request_context(token)


@pytest.mark.asyncio
async def test_transactional_task_publisher_stages_outbox_message() -> None:
    session = AsyncMock()
    queue = AsyncMock()
    publisher = TransactionalTaskPublisher(session, queue)

    message = await publisher.stage(
        "knowledge.chunk",
        {"docId": "doc-1"},
        topic="knowledge",
        idempotency_key="doc-1",
    )

    assert message.event_name == "knowledge.chunk"
    params = session.execute.await_args.args[1]
    assert params["topic"] == "knowledge"
    assert params["idempotency_key"] == "doc-1"
    queue.enqueue.assert_not_called()


class FakeMappingResult:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def mappings(self) -> "FakeMappingResult":
        return self

    def all(self) -> list[dict]:
        return self.rows


@pytest.mark.asyncio
async def test_transactional_task_publisher_dispatches_pending_messages() -> None:
    session = AsyncMock()
    session.execute.side_effect = [
        FakeMappingResult(
            [
                {
                    "id": "msg-1",
                    "event_name": "knowledge.chunk",
                    "payload_json": {"docId": "doc-1"},
                    "idempotency_key": "doc-1",
                },
            ],
        ),
        SimpleNamespace(rowcount=1),
    ]
    queue = AsyncMock()
    queue.enqueue.return_value = TaskMessage(task_id="msg-1", name="knowledge.chunk")
    publisher = TransactionalTaskPublisher(session, queue)

    dispatched = await publisher.dispatch_pending(limit=10)

    assert dispatched == 1
    queue.enqueue.assert_awaited_once_with(
        "knowledge.chunk",
        {"docId": "doc-1"},
        task_id="msg-1",
        idempotency_key="doc-1",
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_rocketmq_worker_returns_retry_status_before_max_attempts(monkeypatch) -> None:
    task = TaskMessage(task_id="task-1", name="demo.task", trace_id="trace-1")
    fake_client = _fake_rocketmq_client(task, reconsume_times=0)
    monkeypatch.setattr("app.infra.task_queue._rocketmq_client", lambda: fake_client)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    fake_client.configure_worker(loop=loop, stop_event=stop_event)
    queue = RocketMQTaskQueue("localhost:9876", "producer", "topic", max_attempts=2)

    async def handler(_: TaskMessage) -> None:
        raise RuntimeError("temporary failure")

    await queue.run_worker({"demo.task": handler}, stop_event)

    assert fake_client.last_status == fake_client.ConsumeStatus.RECONSUME_LATER
    assert queue.consume_traces[0].status == "retry"
    assert queue.dead_letters == []


@pytest.mark.asyncio
async def test_rocketmq_worker_sends_dead_letter_after_max_attempts(monkeypatch) -> None:
    task = TaskMessage(task_id="task-1", name="demo.task", trace_id="trace-1", attempt=1)
    fake_client = _fake_rocketmq_client(task, reconsume_times=1)
    monkeypatch.setattr("app.infra.task_queue._rocketmq_client", lambda: fake_client)
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    fake_client.configure_worker(loop=loop, stop_event=stop_event)
    queue = RocketMQTaskQueue(
        "localhost:9876",
        "producer",
        "topic",
        dlq_topic="topic.DLQ",
        max_attempts=2,
    )

    async def handler(_: TaskMessage) -> None:
        raise RuntimeError("permanent failure")

    await queue.run_worker({"demo.task": handler}, stop_event)

    assert fake_client.last_status == fake_client.ConsumeStatus.CONSUME_SUCCESS
    assert queue.consume_traces[0].status == "dead_letter"
    assert queue.dead_letters[0].task.task_id == "task-1"
    assert fake_client.producer.messages[0].topic == "topic.DLQ"
    assert fake_client.producer.messages[0].properties["TRACE_ID"] == "trace-1"


class _FakeConsumeStatus:
    CONSUME_SUCCESS = "CONSUME_SUCCESS"
    RECONSUME_LATER = "RECONSUME_LATER"


class _FakeRocketMessage:
    def __init__(self, topic: str) -> None:
        self.topic = topic
        self.tags = ""
        self.keys = ""
        self.body = b""
        self.properties: dict[str, str] = {}

    def set_tags(self, tags: str) -> None:
        self.tags = tags

    def set_keys(self, keys: str) -> None:
        self.keys = keys

    def set_body(self, body: bytes) -> None:
        self.body = body

    def set_property(self, key: str, value: str) -> None:
        self.properties[key] = value


class _FakeIncomingMessage:
    def __init__(self, task: TaskMessage, reconsume_times: int) -> None:
        self.body = json.dumps(asdict(task), ensure_ascii=False).encode("utf-8")
        self.reconsume_times = reconsume_times
        self.msg_id = "msg-1"


class _FakeRocketProducer:
    def __init__(self) -> None:
        self.messages: list[_FakeRocketMessage] = []

    def set_name_server_address(self, _: str) -> None:
        return None

    def start(self) -> None:
        return None

    def send_sync(self, message: _FakeRocketMessage) -> None:
        self.messages.append(message)


class _FakeRocketConsumer:
    def __init__(self, client, incoming_message: _FakeIncomingMessage) -> None:
        self.client = client
        self.incoming_message = incoming_message
        self.callback = None
        self.thread: threading.Thread | None = None

    def set_name_server_address(self, _: str) -> None:
        return None

    def subscribe(self, _topic: str, _expression: str, callback) -> None:
        self.callback = callback

    def start(self) -> None:
        assert self.callback is not None

        def run_callback() -> None:
            self.client.last_status = self.callback(self.incoming_message)
            self.client.loop.call_soon_threadsafe(self.client.stop_event.set)

        self.thread = threading.Thread(target=run_callback)
        self.thread.start()

    def shutdown(self) -> None:
        if self.thread is not None:
            self.thread.join(timeout=1)


class _FakeRocketClient:
    ConsumeStatus = _FakeConsumeStatus

    def __init__(self, task: TaskMessage, reconsume_times: int) -> None:
        self.incoming_message = _FakeIncomingMessage(task, reconsume_times)
        self.producer = _FakeRocketProducer()
        self.last_status = None
        self.loop = None
        self.stop_event = None

    def configure_worker(self, *, loop, stop_event) -> None:
        self.loop = loop
        self.stop_event = stop_event

    def PushConsumer(self, _: str) -> _FakeRocketConsumer:
        return _FakeRocketConsumer(self, self.incoming_message)

    def Producer(self, _: str) -> _FakeRocketProducer:
        return self.producer

    def Message(self, topic: str) -> _FakeRocketMessage:
        return _FakeRocketMessage(topic)


def _fake_rocketmq_client(task: TaskMessage, reconsume_times: int) -> _FakeRocketClient:
    return _FakeRocketClient(task, reconsume_times)
