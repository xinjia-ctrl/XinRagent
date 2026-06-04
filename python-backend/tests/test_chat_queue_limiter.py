import asyncio
from types import SimpleNamespace

import pytest

from app.rag.rate_limit import ChatQueueLimiter, InMemoryQueueBackend, QueueStatus


def request_id(value: str) -> str:
    return SimpleNamespace(task_id=value).task_id


@pytest.mark.asyncio
async def test_chat_queue_limiter_waits_until_permit_released() -> None:
    backend = InMemoryQueueBackend()
    limiter = ChatQueueLimiter(
        enabled=True,
        backend=backend,
        max_concurrency=1,
        timeout_seconds=1,
        poll_interval_seconds=0.01,
    )
    first = await limiter.acquire(request_id("task-1"))
    statuses: list[QueueStatus] = []

    second_task = asyncio.create_task(limiter.acquire(request_id("task-2"), statuses.append))
    await asyncio.sleep(0.05)

    assert first.acquired is True
    assert second_task.done() is False
    assert any(status.status == "waiting" and status.position == 1 for status in statuses)

    await first.release()
    second = await asyncio.wait_for(second_task, timeout=1)

    assert second.acquired is True
    assert any(status.status == "acquired" for status in statuses)
    await second.release()


@pytest.mark.asyncio
async def test_chat_queue_limiter_times_out_and_removes_request() -> None:
    backend = InMemoryQueueBackend()
    limiter = ChatQueueLimiter(
        enabled=True,
        backend=backend,
        max_concurrency=1,
        timeout_seconds=0.05,
        poll_interval_seconds=0.01,
    )
    first = await limiter.acquire(request_id("task-1"))
    statuses: list[QueueStatus] = []

    second = await limiter.acquire(request_id("task-2"), statuses.append)

    assert first.acquired is True
    assert second.acquired is False
    assert second.reason == "timeout"
    assert any(status.status == "timeout" for status in statuses)
    assert await backend.position("task-2") is None
    await first.release()


@pytest.mark.asyncio
async def test_disabled_chat_queue_limiter_acquires_immediately() -> None:
    limiter = ChatQueueLimiter.disabled()

    permit = await limiter.acquire(request_id("task-1"))

    assert permit.acquired is True
    await permit.release()
