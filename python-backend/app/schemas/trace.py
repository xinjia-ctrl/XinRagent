from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class TraceRunResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    traceId: str = Field(validation_alias=AliasChoices("trace_id", "traceId"))
    traceName: str | None = Field(default=None, validation_alias=AliasChoices("trace_name", "traceName"))
    entryMethod: str | None = Field(default=None, validation_alias=AliasChoices("entry_method", "entryMethod"))
    conversationId: str | None = Field(default=None, validation_alias=AliasChoices("conversation_id", "conversationId"))
    taskId: str | None = Field(default=None, validation_alias=AliasChoices("task_id", "taskId"))
    userName: str | None = Field(default=None, validation_alias=AliasChoices("user_name", "userName"))
    username: str | None = None
    userId: str | None = Field(default=None, validation_alias=AliasChoices("user_id", "userId"))
    status: str
    errorMessage: str | None = Field(default=None, validation_alias=AliasChoices("error_message", "errorMessage"))
    durationMs: int | None = Field(default=None, validation_alias=AliasChoices("duration_ms", "durationMs"))
    startTime: datetime | None = Field(default=None, validation_alias=AliasChoices("start_time", "startTime"))
    endTime: datetime | None = Field(default=None, validation_alias=AliasChoices("end_time", "endTime"))


class TraceRunPageResponse(BaseModel):
    records: list[TraceRunResponse]
    total: int
    size: int
    current: int
    pages: int


class TraceNodeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    traceId: str | None = Field(default=None, validation_alias=AliasChoices("trace_id", "traceId"))
    nodeId: str = Field(validation_alias=AliasChoices("node_id", "nodeId"))
    parentNodeId: str | None = Field(default=None, validation_alias=AliasChoices("parent_node_id", "parentNodeId"))
    depth: int | None = None
    nodeType: str | None = Field(default=None, validation_alias=AliasChoices("node_type", "nodeType"))
    nodeName: str | None = Field(default=None, validation_alias=AliasChoices("node_name", "nodeName"))
    className: str | None = Field(default=None, validation_alias=AliasChoices("class_name", "className"))
    methodName: str | None = Field(default=None, validation_alias=AliasChoices("method_name", "methodName"))
    status: str
    errorMessage: str | None = Field(default=None, validation_alias=AliasChoices("error_message", "errorMessage"))
    durationMs: int | None = Field(default=None, validation_alias=AliasChoices("duration_ms", "durationMs"))
    startTime: datetime | None = Field(default=None, validation_alias=AliasChoices("start_time", "startTime"))
    endTime: datetime | None = Field(default=None, validation_alias=AliasChoices("end_time", "endTime"))


class TraceDetailResponse(BaseModel):
    run: TraceRunResponse
    nodes: list[TraceNodeResponse]
