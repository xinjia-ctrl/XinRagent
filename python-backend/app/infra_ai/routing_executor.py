from collections.abc import Awaitable, Callable, Sequence
from typing import TypeVar

from app.core.exceptions import RagentException
from app.infra_ai.health_store import ModelHealthStore
from app.infra_ai.model_target import ModelTarget

ResultT = TypeVar("ResultT")


class ModelRoutingExecutor:
    def __init__(self, health_store: ModelHealthStore | None = None) -> None:
        self.health_store = health_store or ModelHealthStore()

    async def execute(
        self,
        targets: Sequence[ModelTarget],
        operation: Callable[[ModelTarget], Awaitable[ResultT]],
    ) -> ResultT:
        last_error: Exception | None = None
        for target in sorted(targets, key=lambda item: item.priority):
            if not self.health_store.can_call(target.name):
                continue

            try:
                result = await operation(target)
            except Exception as exc:
                self.health_store.mark_failure(target.name)
                last_error = exc
                continue

            self.health_store.mark_success(target.name)
            return result

        detail = f": {last_error}" if last_error else ""
        raise RagentException(message=f"所有模型调用失败{detail}", code="AI_REMOTE_ERROR", status_code=502)
