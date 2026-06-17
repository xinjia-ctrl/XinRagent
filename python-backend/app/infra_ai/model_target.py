from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelTarget:
    name: str
    base_url: str
    api_key: str = ""
    model: str = ""
    priority: int = 100
    provider: str = "openai-compatible"
    chat_path: str = "/v1/chat/completions"
    embedding_path: str = "/v1/embeddings"
    rerank_path: str = "/api/v1/services/rerank/text-rerank/text-rerank"
    extra_headers: dict[str, str] = field(default_factory=dict)
    extra_body: dict = field(default_factory=dict)
