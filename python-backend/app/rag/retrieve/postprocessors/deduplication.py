from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve.channels.base import SearchContext
from app.rag.retrieve.postprocessors.base import RetrievalPostProcessor


class DeduplicationPostProcessor(RetrievalPostProcessor):
    async def process(
        self,
        chunks: list[RetrievedChunk],
        _: SearchContext,
    ) -> list[RetrievedChunk]:
        seen: set[str] = set()
        result: list[RetrievedChunk] = []
        for chunk in chunks:
            if chunk.id in seen:
                continue
            seen.add(chunk.id)
            result.append(chunk)
        return result
