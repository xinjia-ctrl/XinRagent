from dataclasses import dataclass
from enum import StrEnum
from time import monotonic, time


class ModelHealthState(StrEnum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ModelHealth:
    state: ModelHealthState = ModelHealthState.CLOSED
    failure_count: int = 0
    success_count: int = 0
    total_call_count: int = 0
    consecutive_failure_count: int = 0
    opened_at: float | None = None
    last_success_at: float | None = None
    last_failure_at: float | None = None
    last_probe_at: float | None = None
    last_latency_ms: float | None = None
    avg_latency_ms: float | None = None
    last_first_token_ms: float | None = None
    last_error: str | None = None


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

    def mark_success(
        self,
        target_name: str,
        *,
        latency_ms: float | None = None,
        first_token_ms: float | None = None,
        is_probe: bool = False,
    ) -> None:
        health = self._items.setdefault(target_name, ModelHealth())
        health.state = ModelHealthState.CLOSED
        health.success_count += 1
        health.total_call_count += 1
        health.consecutive_failure_count = 0
        health.opened_at = None
        health.last_success_at = time()
        health.last_error = None
        if is_probe:
            health.last_probe_at = health.last_success_at
        self._record_latency(health, latency_ms, first_token_ms)

    def mark_failure(
        self,
        target_name: str,
        *,
        error: Exception | str | None = None,
        latency_ms: float | None = None,
        is_probe: bool = False,
    ) -> None:
        health = self._items.setdefault(target_name, ModelHealth())
        health.failure_count += 1
        health.total_call_count += 1
        health.consecutive_failure_count += 1
        health.last_failure_at = time()
        health.last_error = str(error) if error is not None else None
        if is_probe:
            health.last_probe_at = health.last_failure_at
        self._record_latency(health, latency_ms, None)
        if health.consecutive_failure_count >= self.failure_threshold:
            health.state = ModelHealthState.OPEN
            health.opened_at = monotonic()

    def get(self, target_name: str) -> ModelHealth:
        return self._items.setdefault(target_name, ModelHealth())

    def snapshot(self) -> list[dict[str, object]]:
        return [
            {
                "name": name,
                "state": health.state.value,
                "totalCalls": health.total_call_count,
                "successCount": health.success_count,
                "failureCount": health.failure_count,
                "consecutiveFailureCount": health.consecutive_failure_count,
                "lastLatencyMs": health.last_latency_ms,
                "avgLatencyMs": health.avg_latency_ms,
                "lastFirstTokenMs": health.last_first_token_ms,
                "lastSuccessAt": health.last_success_at,
                "lastFailureAt": health.last_failure_at,
                "lastProbeAt": health.last_probe_at,
                "lastError": health.last_error,
            }
            for name, health in sorted(self._items.items())
        ]

    @staticmethod
    def _record_latency(
        health: ModelHealth,
        latency_ms: float | None,
        first_token_ms: float | None,
    ) -> None:
        if latency_ms is not None:
            health.last_latency_ms = latency_ms
            if health.avg_latency_ms is None:
                health.avg_latency_ms = latency_ms
            else:
                health.avg_latency_ms = (health.avg_latency_ms + latency_ms) / 2
        if first_token_ms is not None:
            health.last_first_token_ms = first_token_ms
