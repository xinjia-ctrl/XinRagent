from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "ragent-python"
    app_env: str = "dev"
    app_host: str = "0.0.0.0"
    app_port: int = 9090
    api_prefix: str = "/api/ragent"

    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/ragent"
    redis_url: str = "redis://localhost:6379/0"

    auth_secret_key: str = Field(default="ragent-dev-secret", repr=False)
    auth_token_expire_seconds: int = 86400

    rag_vector_type: str = "pg"
    rag_default_collection_name: str = "rag_default_store"
    rag_default_dimension: int = 1536
    rag_default_top_k: int = 5
    rag_sse_timeout_ms: int = 300000

    ai_bailian_url: str = "https://dashscope.aliyuncs.com"
    ai_bailian_api_key: str = Field(default="", repr=False)
    ai_siliconflow_url: str = "https://api.siliconflow.cn"
    ai_siliconflow_api_key: str = Field(default="", repr=False)
    ai_ollama_url: str = "http://localhost:11434"

    ai_chat_default_model: str = "qwen3-max"
    ai_embedding_default_model: str = "qwen-emb-8b"
    ai_rerank_default_model: str = "qwen3-rerank"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
