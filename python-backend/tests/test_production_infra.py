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
