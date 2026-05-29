from typing import Protocol

from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve.channels.base import SearchContext


class RetrievalPostProcessor(Protocol):
    async def process(
        self,
        chunks: list[RetrievedChunk],
        context: SearchContext,
    ) -> list[RetrievedChunk]:
        ...
