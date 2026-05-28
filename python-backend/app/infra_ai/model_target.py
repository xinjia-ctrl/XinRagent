from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelTarget:
    name: str
    base_url: str
    api_key: str = ""
    model: str = ""
    priority: int = 100
    provider: str = "openai-compatible"
    extra_headers: dict[str, str] = field(default_factory=dict)
