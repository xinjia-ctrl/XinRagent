import asyncio
from dataclasses import dataclass


@dataclass
class StreamTaskState:
    task_id: str
    task: asyncio.Task


class StreamTaskManager:
    def __init__(self) -> None:
        self._tasks: dict[str, StreamTaskState] = {}

    def register(self, task_id: str, task: asyncio.Task) -> None:
        self._tasks[task_id] = StreamTaskState(task_id=task_id, task=task)
        task.add_done_callback(lambda _: self.remove(task_id))

    def cancel(self, task_id: str) -> bool:
        state = self._tasks.get(task_id)
        if state is None:
            return False
        state.task.cancel()
        return True

    def remove(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)

    def exists(self, task_id: str) -> bool:
        return task_id in self._tasks


stream_task_manager = StreamTaskManager()
