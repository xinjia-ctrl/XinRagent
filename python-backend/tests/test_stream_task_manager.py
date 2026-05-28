import asyncio

import pytest

from app.rag.stream import StreamTaskManager


@pytest.mark.asyncio
async def test_stream_task_manager_registers_and_removes_done_task() -> None:
    manager = StreamTaskManager()
    task = asyncio.create_task(asyncio.sleep(0))

    manager.register("task-1", task)

    assert manager.exists("task-1") is True
    await task
    await asyncio.sleep(0)
    assert manager.exists("task-1") is False


@pytest.mark.asyncio
async def test_stream_task_manager_cancels_existing_task() -> None:
    manager = StreamTaskManager()
    task = asyncio.create_task(asyncio.sleep(60))

    manager.register("task-1", task)

    assert manager.cancel("task-1") is True
    await asyncio.sleep(0)
    assert task.cancelled() is True


def test_stream_task_manager_returns_false_for_missing_task() -> None:
    manager = StreamTaskManager()

    assert manager.cancel("missing") is False
