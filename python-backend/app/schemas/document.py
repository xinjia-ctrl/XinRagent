from datetime import datetime

from pydantic import AliasChoices, BaseModel, ConfigDict, Field


class KnowledgeDocumentResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kbId: str = Field(validation_alias=AliasChoices("kb_id", "kbId"))
    docName: str = Field(validation_alias=AliasChoices("doc_name", "docName"))
    sourceType: str | None = Field(default=None, validation_alias=AliasChoices("source_type", "sourceType"))
    sourceLocation: str | None = Field(
        default=None,
        validation_alias=AliasChoices("source_location", "sourceLocation"),
    )
    scheduleEnabled: int | bool | None = Field(
        default=None,
        validation_alias=AliasChoices("schedule_enabled", "scheduleEnabled"),
    )
    scheduleCron: str | None = Field(default=None, validation_alias=AliasChoices("schedule_cron", "scheduleCron"))
    enabled: bool | None = True
    chunkCount: int = Field(default=0, validation_alias=AliasChoices("chunk_count", "chunkCount"))
    fileUrl: str | None = Field(default=None, validation_alias=AliasChoices("file_url", "fileUrl"))
    fileType: str | None = Field(default=None, validation_alias=AliasChoices("file_type", "fileType"))
    fileSize: int | None = Field(default=None, validation_alias=AliasChoices("file_size", "fileSize"))
    processMode: str | None = Field(default=None, validation_alias=AliasChoices("process_mode", "processMode"))
    chunkStrategy: str | None = Field(default=None, validation_alias=AliasChoices("chunk_strategy", "chunkStrategy"))
    chunkConfig: str | dict | None = Field(default=None, validation_alias=AliasChoices("chunk_config", "chunkConfig"))
    pipelineId: str | int | None = Field(default=None, validation_alias=AliasChoices("pipeline_id", "pipelineId"))
    status: str | None = None
    createdBy: str | None = Field(default=None, validation_alias=AliasChoices("created_by", "createdBy"))
    updatedBy: str | None = Field(default=None, validation_alias=AliasChoices("updated_by", "updatedBy"))
    createTime: datetime | None = Field(default=None, validation_alias=AliasChoices("create_time", "createTime"))
    updateTime: datetime | None = Field(default=None, validation_alias=AliasChoices("update_time", "updateTime"))


class KnowledgeDocumentPageResponse(BaseModel):
    records: list[KnowledgeDocumentResponse]
    total: int
    size: int
    current: int
    pages: int


class KnowledgeDocumentSearchItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kbId: str = Field(validation_alias=AliasChoices("kb_id", "kbId"))
    docName: str = Field(validation_alias=AliasChoices("doc_name", "docName"))
    kbName: str | None = Field(default=None, validation_alias=AliasChoices("kb_name", "kbName"))


class KnowledgeDocumentUpdateRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    doc_name: str | None = Field(default=None, validation_alias=AliasChoices("doc_name", "docName"))
    process_mode: str | None = Field(default=None, validation_alias=AliasChoices("process_mode", "processMode"))
    chunk_strategy: str | None = Field(default=None, validation_alias=AliasChoices("chunk_strategy", "chunkStrategy"))
    chunk_config: str | None = Field(default=None, validation_alias=AliasChoices("chunk_config", "chunkConfig"))
    pipeline_id: str | None = Field(default=None, validation_alias=AliasChoices("pipeline_id", "pipelineId"))
    source_location: str | None = Field(
        default=None,
        validation_alias=AliasChoices("source_location", "sourceLocation"),
    )
    schedule_enabled: int | bool | None = Field(
        default=None,
        validation_alias=AliasChoices("schedule_enabled", "scheduleEnabled"),
    )
    schedule_cron: str | None = Field(default=None, validation_alias=AliasChoices("schedule_cron", "scheduleCron"))


class KnowledgeChunkResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    kbId: str | None = Field(default=None, validation_alias=AliasChoices("kb_id", "kbId"))
    docId: str = Field(validation_alias=AliasChoices("doc_id", "docId"))
    chunkIndex: int | None = Field(default=None, validation_alias=AliasChoices("chunk_index", "chunkIndex"))
    content: str | None = None
    contentHash: str | None = Field(default=None, validation_alias=AliasChoices("content_hash", "contentHash"))
    charCount: int | None = Field(default=None, validation_alias=AliasChoices("char_count", "charCount"))
    tokenCount: int | None = Field(default=None, validation_alias=AliasChoices("token_count", "tokenCount"))
    enabled: int | bool | None = True
    createTime: datetime | None = Field(default=None, validation_alias=AliasChoices("create_time", "createTime"))
    updateTime: datetime | None = Field(default=None, validation_alias=AliasChoices("update_time", "updateTime"))


class KnowledgeChunkPageResponse(BaseModel):
    records: list[KnowledgeChunkResponse]
    total: int
    size: int
    current: int
    pages: int


class KnowledgeChunkCreateRequest(BaseModel):
    content: str = Field(min_length=1)
    index: int | None = None
    chunkId: str | None = Field(default=None, validation_alias=AliasChoices("chunk_id", "chunkId"))


class KnowledgeChunkUpdateRequest(BaseModel):
    content: str = Field(min_length=1)


class KnowledgeChunkBatchEnableRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    chunkIds: list[str | int] = Field(validation_alias=AliasChoices("chunk_ids", "chunkIds"))


class KnowledgeDocumentChunkLogResponse(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    docId: str = Field(validation_alias=AliasChoices("doc_id", "docId"))
    status: str
    processMode: str | None = Field(default=None, validation_alias=AliasChoices("process_mode", "processMode"))
    chunkStrategy: str | None = Field(default=None, validation_alias=AliasChoices("chunk_strategy", "chunkStrategy"))
    pipelineId: str | None = Field(default=None, validation_alias=AliasChoices("pipeline_id", "pipelineId"))
    pipelineName: str | None = Field(default=None, validation_alias=AliasChoices("pipeline_name", "pipelineName"))
    extractDuration: int | None = Field(
        default=None,
        validation_alias=AliasChoices("extract_duration", "extractDuration"),
    )
    chunkDuration: int | None = Field(default=None, validation_alias=AliasChoices("chunk_duration", "chunkDuration"))
    embedDuration: int | None = Field(default=None, validation_alias=AliasChoices("embed_duration", "embedDuration"))
    persistDuration: int | None = Field(
        default=None,
        validation_alias=AliasChoices("persist_duration", "persistDuration"),
    )
    otherDuration: int | None = Field(default=None, validation_alias=AliasChoices("other_duration", "otherDuration"))
    totalDuration: int | None = Field(default=None, validation_alias=AliasChoices("total_duration", "totalDuration"))
    chunkCount: int | None = Field(default=None, validation_alias=AliasChoices("chunk_count", "chunkCount"))
    errorMessage: str | None = Field(default=None, validation_alias=AliasChoices("error_message", "errorMessage"))
    startTime: datetime | None = Field(default=None, validation_alias=AliasChoices("start_time", "startTime"))
    endTime: datetime | None = Field(default=None, validation_alias=AliasChoices("end_time", "endTime"))
    createTime: datetime | None = Field(default=None, validation_alias=AliasChoices("create_time", "createTime"))


class KnowledgeDocumentChunkLogPageResponse(BaseModel):
    records: list[KnowledgeDocumentChunkLogResponse]
    total: int
    size: int
    current: int
    pages: int
