from app.core.config import settings
from app.infra_ai.model_target import ModelTarget


def default_chat_targets() -> list[ModelTarget]:
    return [
        ModelTarget(
            name="bailian-chat",
            base_url=settings.ai_bailian_url,
            api_key=settings.ai_bailian_api_key,
            model=settings.ai_chat_default_model,
            priority=10,
            provider="bailian",
        ),
        ModelTarget(
            name="siliconflow-chat",
            base_url=settings.ai_siliconflow_url,
            api_key=settings.ai_siliconflow_api_key,
            model=settings.ai_chat_default_model,
            priority=20,
            provider="siliconflow",
        ),
        ModelTarget(
            name="ollama-chat",
            base_url=settings.ai_ollama_url,
            model=settings.ai_chat_default_model,
            priority=30,
            provider="ollama",
        ),
    ]


def default_embedding_targets() -> list[ModelTarget]:
    return [
        ModelTarget(
            name="bailian-embedding",
            base_url=settings.ai_bailian_url,
            api_key=settings.ai_bailian_api_key,
            model=settings.ai_embedding_default_model,
            priority=10,
            provider="bailian",
        ),
        ModelTarget(
            name="siliconflow-embedding",
            base_url=settings.ai_siliconflow_url,
            api_key=settings.ai_siliconflow_api_key,
            model=settings.ai_embedding_default_model,
            priority=20,
            provider="siliconflow",
        ),
    ]
