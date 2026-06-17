from app.core.config import settings
from app.infra_ai.model_target import ModelTarget


def default_chat_targets() -> list[ModelTarget]:
    return [
        ModelTarget(
            name="glm-4.7",
            base_url=settings.ai_siliconflow_url,
            api_key=settings.ai_siliconflow_api_key,
            model="Pro/zai-org/GLM-4.7",
            priority=0,
            provider="siliconflow",
            chat_path="/v1/chat/completions",
        ),
        ModelTarget(
            name="qwen-plus",
            base_url=settings.ai_bailian_url,
            api_key=settings.ai_bailian_api_key,
            model="qwen-plus-latest",
            priority=1,
            provider="bailian",
            chat_path="/compatible-mode/v1/chat/completions",
        ),
        ModelTarget(
            name="qwen3-local",
            base_url=settings.ai_ollama_url,
            model="qwen3:8b-fp16",
            priority=2,
            provider="ollama",
            chat_path="/v1/chat/completions",
        ),
        ModelTarget(
            name="qwen3-max",
            base_url=settings.ai_bailian_url,
            api_key=settings.ai_bailian_api_key,
            model="qwen3-max",
            priority=3,
            provider="bailian",
            chat_path="/compatible-mode/v1/chat/completions",
        ),
    ]


def default_embedding_targets() -> list[ModelTarget]:
    return [
        ModelTarget(
            name="qwen-emb-8b",
            base_url=settings.ai_siliconflow_url,
            api_key=settings.ai_siliconflow_api_key,
            model="Qwen/Qwen3-Embedding-8B",
            priority=1,
            provider="siliconflow",
            embedding_path="/v1/embeddings",
            extra_body={"dimensions": settings.rag_default_dimension},
        ),
        ModelTarget(
            name="qwen-emb-local",
            base_url=settings.ai_ollama_url,
            model="qwen3-embedding:8b-fp16",
            priority=2,
            provider="ollama",
            embedding_path="/v1/embeddings",
            extra_body={"dimensions": settings.rag_default_dimension},
        ),
    ]


def default_rerank_targets() -> list[ModelTarget]:
    return [
        ModelTarget(
            name="qwen3-rerank",
            base_url=settings.ai_bailian_url,
            api_key=settings.ai_bailian_api_key,
            model=settings.ai_rerank_default_model,
            priority=1,
            provider="bailian",
            rerank_path="/api/v1/services/rerank/text-rerank/text-rerank",
        ),
        ModelTarget(
            name="rerank-noop",
            base_url="",
            model="noop",
            priority=100,
            provider="noop",
        ),
    ]
