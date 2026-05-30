from pydantic import BaseModel


class TraceRunResponse(BaseModel):
    trace_id: str
    trace_name: str | None = None
    conversation_id: str | None = None
    task_id: str | None = None
    user_id: str | None = None
    status: str
    error_message: str | None = None
    duration_ms: int | None = None


class TraceNodeResponse(BaseModel):
    node_id: str
    node_name: str | None = None
    node_type: str | None = None
    status: str
    duration_ms: int | None = None
    error_message: str | None = None


class TraceDetailResponse(BaseModel):
    run: TraceRunResponse
    nodes: list[TraceNodeResponse]
