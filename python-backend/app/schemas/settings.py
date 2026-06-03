from pydantic import BaseModel, ConfigDict, Field


class UploadSettings(BaseModel):
    maxFileSize: int
    maxRequestSize: int


class RagDefaultSettings(BaseModel):
    collectionName: str
    dimension: int
    metricType: str


class RagQueryRewriteSettings(BaseModel):
    enabled: bool
    maxHistoryMessages: int
    maxHistoryChars: int


class RagRateLimitGlobalSettings(BaseModel):
    enabled: bool
    maxConcurrent: int
    maxWaitSeconds: int
    leaseSeconds: int
    pollIntervalMs: int


class RagRateLimitSettings(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    global_: RagRateLimitGlobalSettings = Field(serialization_alias="global")


class RagMemorySettings(BaseModel):
    historyKeepTurns: int
    summaryStartTurns: int
    summaryEnabled: bool
    ttlMinutes: int
    summaryMaxChars: int
    titleMaxLength: int


class RagSettings(BaseModel):
    default: RagDefaultSettings
    queryRewrite: RagQueryRewriteSettings
    rateLimit: RagRateLimitSettings
    memory: RagMemorySettings


class ModelCandidate(BaseModel):
    id: str
    provider: str
    model: str
    url: str | None = None
    dimension: int | None = None
    priority: int | None = None
    enabled: bool | None = None
    supportsThinking: bool | None = None


class ModelGroup(BaseModel):
    defaultModel: str | None = None
    deepThinkingModel: str | None = None
    candidates: list[ModelCandidate]


class AiProviderSettings(BaseModel):
    url: str
    apiKey: str | None = None
    endpoints: dict[str, str]


class AiSelectionSettings(BaseModel):
    failureThreshold: int
    openDurationMs: int


class AiStreamSettings(BaseModel):
    messageChunkSize: int


class AiSettings(BaseModel):
    providers: dict[str, AiProviderSettings]
    selection: AiSelectionSettings
    stream: AiStreamSettings
    chat: ModelGroup
    embedding: ModelGroup
    rerank: ModelGroup


class SystemSettingsResponse(BaseModel):
    upload: UploadSettings
    rag: RagSettings
    ai: AiSettings
