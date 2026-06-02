from datetime import datetime
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class UploadedDocumentResponse(BaseModel):
    kb_id: str
    doc_id: str
    file_name: str
    file_type: str
    file_size: int
    storage_path: str
    status: str = "uploaded"
    chunk_count: int = 0


class IngestionPipelineNodePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    node_id: str = Field(validation_alias=AliasChoices("node_id", "nodeId"))
    node_type: str = Field(validation_alias=AliasChoices("node_type", "nodeType"))
    settings: dict[str, Any] | None = None
    condition: dict[str, Any] | None = None
    next_node_id: str | None = Field(default=None, validation_alias=AliasChoices("next_node_id", "nextNodeId"))


class IngestionPipelinePayload(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    nodes: list[IngestionPipelineNodePayload] | None = None


class IngestionPipelineNodeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    nodeId: str = Field(validation_alias=AliasChoices("node_id", "nodeId"))
    nodeType: str = Field(validation_alias=AliasChoices("node_type", "nodeType"))
    settings: dict[str, Any] | None = None
    condition: dict[str, Any] | None = None
    nextNodeId: str | None = Field(default=None, validation_alias=AliasChoices("next_node_id", "nextNodeId"))


class IngestionPipelineResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    name: str
    description: str | None = None
    createdBy: str | None = Field(default=None, validation_alias=AliasChoices("created_by", "createdBy"))
    nodes: list[IngestionPipelineNodeResponse] = Field(default_factory=list)
    createTime: datetime | None = Field(default=None, validation_alias=AliasChoices("create_time", "createTime"))
    updateTime: datetime | None = Field(default=None, validation_alias=AliasChoices("update_time", "updateTime"))


class IngestionPipelinePageResponse(BaseModel):
    records: list[IngestionPipelineResponse]
    total: int
    size: int
    current: int
    pages: int


class IngestionTaskSource(BaseModel):
    type: str
    location: str
    fileName: str | None = Field(default=None, validation_alias=AliasChoices("file_name", "fileName"))
    credentials: dict[str, str] | None = None


class IngestionTaskCreateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    pipeline_id: str = Field(validation_alias=AliasChoices("pipeline_id", "pipelineId"))
    source: IngestionTaskSource
    metadata: dict[str, Any] | None = None
    vectorSpaceId: dict[str, Any] | None = Field(default=None, validation_alias=AliasChoices("vector_space_id", "vectorSpaceId"))


class IngestionTaskNodeLog(BaseModel):
    nodeId: str = Field(validation_alias=AliasChoices("node_id", "nodeId"))
    nodeType: str = Field(validation_alias=AliasChoices("node_type", "nodeType"))
    message: str | None = None
    durationMs: int | None = Field(default=None, validation_alias=AliasChoices("duration_ms", "durationMs"))
    success: bool | None = None
    error: str | None = None


class IngestionTaskResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    pipelineId: str = Field(validation_alias=AliasChoices("pipeline_id", "pipelineId"))
    sourceType: str | None = Field(default=None, validation_alias=AliasChoices("source_type", "sourceType"))
    sourceLocation: str | None = Field(default=None, validation_alias=AliasChoices("source_location", "sourceLocation"))
    sourceFileName: str | None = Field(default=None, validation_alias=AliasChoices("source_file_name", "sourceFileName"))
    status: str | None = None
    chunkCount: int | None = Field(default=None, validation_alias=AliasChoices("chunk_count", "chunkCount"))
    errorMessage: str | None = Field(default=None, validation_alias=AliasChoices("error_message", "errorMessage"))
    logs: list[IngestionTaskNodeLog] | None = None
    metadata: dict[str, Any] | None = None
    startedAt: datetime | None = Field(default=None, validation_alias=AliasChoices("started_at", "startedAt"))
    completedAt: datetime | None = Field(default=None, validation_alias=AliasChoices("completed_at", "completedAt"))
    createdBy: str | None = Field(default=None, validation_alias=AliasChoices("created_by", "createdBy"))
    createTime: datetime | None = Field(default=None, validation_alias=AliasChoices("create_time", "createTime"))
    updateTime: datetime | None = Field(default=None, validation_alias=AliasChoices("update_time", "updateTime"))


class IngestionTaskPageResponse(BaseModel):
    records: list[IngestionTaskResponse]
    total: int
    size: int
    current: int
    pages: int


class IngestionTaskNodeResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    taskId: str = Field(validation_alias=AliasChoices("task_id", "taskId"))
    pipelineId: str = Field(validation_alias=AliasChoices("pipeline_id", "pipelineId"))
    nodeId: str = Field(validation_alias=AliasChoices("node_id", "nodeId"))
    nodeType: str = Field(validation_alias=AliasChoices("node_type", "nodeType"))
    nodeOrder: int | None = Field(default=None, validation_alias=AliasChoices("node_order", "nodeOrder"))
    status: str | None = None
    durationMs: int | None = Field(default=None, validation_alias=AliasChoices("duration_ms", "durationMs"))
    message: str | None = None
    errorMessage: str | None = Field(default=None, validation_alias=AliasChoices("error_message", "errorMessage"))
    output: dict[str, Any] | None = None
    createTime: datetime | None = Field(default=None, validation_alias=AliasChoices("create_time", "createTime"))
    updateTime: datetime | None = Field(default=None, validation_alias=AliasChoices("update_time", "updateTime"))


class IngestionResultResponse(BaseModel):
    taskId: str = Field(validation_alias=AliasChoices("task_id", "taskId"))
    pipelineId: str = Field(validation_alias=AliasChoices("pipeline_id", "pipelineId"))
    status: str | None = None
    chunkCount: int | None = Field(default=None, validation_alias=AliasChoices("chunk_count", "chunkCount"))
    message: str | None = None
