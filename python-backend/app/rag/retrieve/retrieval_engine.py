from app.core.config import settings
from app.rag.intent import IntentMatch
from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve.channels.base import SearchContext
from app.rag.retrieve.multi_channel_retrieval_engine import MultiChannelRetrievalEngine


class RetrievalEngine:
    def __init__(self, multi_channel_engine: MultiChannelRetrievalEngine) -> None:
        self.multi_channel_engine = multi_channel_engine

    async def retrieve(
        self,
        query: str,
        original_query: str | None = None,
        intents: list[IntentMatch] | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        context = SearchContext(
            query=query,
            top_k=top_k or settings.rag_default_top_k,
            original_query=original_query,
            conversation_id=conversation_id,
            user_id=user_id,
            intents=intents,
        )
        return await self.multi_channel_engine.retrieve_knowledge_channels(context)
