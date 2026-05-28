from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class RerankDocument:
    id: str
    content: str
    score: float = 0.0
    metadata: dict | None = None


@dataclass(frozen=True)
class RerankRequest:
    query: str
    documents: Sequence[RerankDocument]
    model: str = ""
    top_n: int | None = None
    extra_body: dict | None = None


@dataclass(frozen=True)
class RerankResponse:
    documents: list[RerankDocument]
    model: str = ""
    raw: dict = field(default_factory=dict)


class RerankClient(Protocol):
    async def rerank(self, request: RerankRequest) -> RerankResponse:
        ...
