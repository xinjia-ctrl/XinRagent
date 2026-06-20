from pydantic import BaseModel


class ModelHealthItem(BaseModel):
    name: str
    provider: str
    model: str
    priority: int
    state: str
    totalCalls: int
    successCount: int
    failureCount: int
    consecutiveFailureCount: int
    lastLatencyMs: float | None = None
    avgLatencyMs: float | None = None
    lastFirstTokenMs: float | None = None
    lastSuccessAt: float | None = None
    lastFailureAt: float | None = None
    lastProbeAt: float | None = None
    lastError: str | None = None


class ModelProbeResult(BaseModel):
    name: str
    success: bool
    latencyMs: float
    firstTokenMs: float | None = None
    error: str | None = None
