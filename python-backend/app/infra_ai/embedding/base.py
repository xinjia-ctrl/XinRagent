from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingRequest:
    texts: Sequence[str]
    model: str
    extra_body: dict | None = None


@dataclass(frozen=True)
class EmbeddingResponse:
    vectors: list[list[float]]
    model: str
    raw: dict = field(default_factory=dict)


class EmbeddingClient(Protocol):
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        ...
