from app.rag.retrieve import PgVectorStoreService, RetrievedChunk
from app.rag.retrieve.channels.base import SearchContext, SearchChannel


class VectorGlobalSearchChannel(SearchChannel):
    name = "vector_global"

    def __init__(self, vector_store: PgVectorStoreService) -> None:
        self.vector_store = vector_store

    async def search(self, context: SearchContext) -> list[RetrievedChunk]:
        return await self.vector_store.search(context.query, top_k=context.top_k)
