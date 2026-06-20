from app.rag.retrieve import RetrievedChunk, VectorStoreService
from app.rag.retrieve.channels.base import SearchContext, SearchChannel


class VectorGlobalSearchChannel(SearchChannel):
    name = "vector_global"

    def __init__(self, vector_store: VectorStoreService) -> None:
        self.vector_store = vector_store

    async def search(self, context: SearchContext) -> list[RetrievedChunk]:
        chunks = await self.vector_store.search(context.query, top_k=context.top_k)
        return [
            RetrievedChunk(
                id=chunk.id,
                content=chunk.content,
                score=chunk.score,
                metadata={**chunk.metadata, "channel": self.name},
            )
            for chunk in chunks
        ]
