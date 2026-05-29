from dataclasses import dataclass
from typing import Protocol

from app.rag.retrieve import RetrievedChunk


@dataclass(frozen=True)
class SearchContext:
    query: str
    top_k: int
    conversation_id: str | None = None
    user_id: str | None = None


class SearchChannel(Protocol):
    name: str

    async def search(self, context: SearchContext) -> list[RetrievedChunk]:
        ...
