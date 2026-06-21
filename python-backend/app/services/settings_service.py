from app.core.config import settings
from app.infra_ai.config import default_chat_targets, default_embedding_targets
from app.infra_ai.model_target import ModelTarget
from app.schemas.settings import (
    AiProviderSettings,
    AiSelectionSettings,
    AiSettings,
    AiStreamSettings,
    ModelCandidate,
    ModelGroup,
    RagDefaultSettings,
    RagMemorySettings,
    RagQueryRewriteSettings,
    RagRateLimitGlobalSettings,
    RagRateLimitSettings,
    RagSettings,
    SystemSettingsResponse,
    UploadSettings,
)


class SettingsService:
    async def get_settings(self) -> SystemSettingsResponse:
        chat_targets = default_chat_targets()
        embedding_targets = default_embedding_targets()
        rerank_targets = [
            ModelTarget(
                name="qwen3-rerank",
                base_url=settings.ai_bailian_url,
                api_key=settings.ai_bailian_api_key,
                model="qwen3-rerank",
                priority=1,
                provider="bailian",
            ),
            ModelTarget(
                name="rerank-noop",
                base_url="",
                model="noop",
                priority=100,
                provider="noop",
            ),
        ]
        return SystemSettingsResponse(
            upload=UploadSettings(
                maxFileSize=50 * 1024 * 1024,
                maxRequestSize=60 * 1024 * 1024,
            ),
            rag=RagSettings(
                default=RagDefaultSettings(
                    collectionName=settings.rag_default_collection_name,
                    dimension=settings.rag_default_dimension,
                    metricType="cosine",
                ),
                queryRewrite=RagQueryRewriteSettings(
                    enabled=True,
                    maxHistoryMessages=6,
                    maxHistoryChars=4000,
                ),
                rateLimit=RagRateLimitSettings(
                    global_=RagRateLimitGlobalSettings(
                        enabled=False,
                        maxConcurrent=100,
                        maxWaitSeconds=30,
                        leaseSeconds=120,
                        pollIntervalMs=250,
                    ),
                ),
                memory=RagMemorySettings(
                    historyKeepTurns=settings.rag_memory_summary_keep_recent_messages,
                    summaryStartTurns=settings.rag_memory_summary_start_messages,
                    summaryEnabled=settings.rag_memory_summary_enabled,
                    ttlMinutes=24 * 60,
                    summaryMaxChars=settings.rag_memory_summary_max_chars,
                    titleMaxLength=30,
                ),
            ),
            ai=AiSettings(
                providers={
                    "bailian": AiProviderSettings(
                        url=settings.ai_bailian_url,
                        apiKey=self._mask_key(settings.ai_bailian_api_key),
                        endpoints={
                            "chat": "/compatible-mode/v1/chat/completions",
                            "rerank": "/api/v1/services/rerank/text-rerank/text-rerank",
                        },
                    ),
                    "siliconflow": AiProviderSettings(
                        url=settings.ai_siliconflow_url,
                        apiKey=self._mask_key(settings.ai_siliconflow_api_key),
                        endpoints={"chat": "/v1/chat/completions", "embedding": "/v1/embeddings"},
                    ),
                    "ollama": AiProviderSettings(
                        url=settings.ai_ollama_url,
                        endpoints={"chat": "/v1/chat/completions"},
                    ),
                },
                selection=AiSelectionSettings(failureThreshold=3, openDurationMs=60_000),
                stream=AiStreamSettings(messageChunkSize=1),
                chat=ModelGroup(
                    defaultModel=settings.ai_chat_default_model,
                    deepThinkingModel=settings.ai_deep_thinking_model,
                    candidates=[
                        self._candidate(
                            target,
                            supports_thinking=target.name in {"glm-4.7", "qwen3-max"},
                        )
                        for target in chat_targets
                    ],
                ),
                embedding=ModelGroup(
                    defaultModel=settings.ai_embedding_default_model,
                    candidates=[
                        self._candidate(target, dimension=settings.rag_default_dimension)
                        for target in embedding_targets
                    ],
                ),
                rerank=ModelGroup(
                    defaultModel=settings.ai_rerank_default_model,
                    candidates=[self._candidate(target) for target in rerank_targets],
                ),
            ),
        )

    @staticmethod
    def _candidate(
        target: ModelTarget,
        dimension: int | None = None,
        supports_thinking: bool | None = None,
    ) -> ModelCandidate:
        return ModelCandidate(
            id=target.name,
            provider=target.provider,
            model=target.model,
            url=target.base_url,
            dimension=dimension,
            priority=target.priority,
            enabled=True,
            supportsThinking=supports_thinking,
        )

    @staticmethod
    def _mask_key(api_key: str) -> str | None:
        if not api_key:
            return None
        return "***"
