import asyncio
from collections.abc import Sequence

from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve.channels.base import SearchChannel, SearchContext
from app.rag.retrieve.postprocessors.base import RetrievalPostProcessor
from app.rag.retrieve.postprocessors.deduplication import DeduplicationPostProcessor


class MultiChannelRetrievalEngine:
    def __init__(
        self,
        channels: Sequence[SearchChannel],
        postprocessors: Sequence[RetrievalPostProcessor] | None = None,
    ) -> None:
        self.channels = list(channels)
        self.postprocessors = list(postprocessors or [DeduplicationPostProcessor()])

    async def retrieve_knowledge_channels(self, context: SearchContext) -> list[RetrievedChunk]:
        if not self.channels:
            return []

        channel_results = await asyncio.gather(
            *(channel.search(context) for channel in self.channels),
            return_exceptions=True,
        )
        chunks = [
            chunk
            for result in channel_results
            if not isinstance(result, Exception)
            for chunk in result
        ]
        chunks.sort(key=lambda item: item.score, reverse=True)

        for postprocessor in self.postprocessors:
            chunks = await postprocessor.process(chunks, context)
        return chunks[: context.top_k]
