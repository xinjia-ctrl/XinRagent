from dataclasses import dataclass
from enum import StrEnum
from time import monotonic


class ModelHealthState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ModelHealth:
    state: ModelHealthState = ModelHealthState.CLOSED
    failure_count: int = 0
    opened_at: float | None = None


class ModelHealthStore:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0) -> None:
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._items: dict[str, ModelHealth] = {}

    def can_call(self, target_name: str) -> bool:
        health = self._items.get(target_name)
        if health is None or health.state == ModelHealthState.CLOSED:
            return True
        if health.state == ModelHealthState.HALF_OPEN:
            return True
        if health.opened_at is None:
            return False
        if monotonic() - health.opened_at >= self.cooldown_seconds:
            health.state = ModelHealthState.HALF_OPEN
            return True
        return False

    def mark_success(self, target_name: str) -> None:
        self._items[target_name] = ModelHealth()

    def mark_failure(self, target_name: str) -> None:
        health = self._items.setdefault(target_name, ModelHealth())
        health.failure_count += 1
        if health.failure_count >= self.failure_threshold:
            health.state = ModelHealthState.OPEN
            health.opened_at = monotonic()

    def get(self, target_name: str) -> ModelHealth:
        return self._items.setdefault(target_name, ModelHealth())
