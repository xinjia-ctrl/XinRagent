from app.rag.retrieve import PgVectorStoreService, RetrievedChunk
from app.rag.retrieve.channels.base import SearchChannel, SearchContext


class IntentDirectedSearchChannel(SearchChannel):
    name = "intent_directed"

    def __init__(self, vector_store: PgVectorStoreService) -> None:
        self.vector_store = vector_store

    async def search(self, context: SearchContext) -> list[RetrievedChunk]:
        intents = [intent for intent in context.intents or [] if intent.is_knowledge]
        if not intents:
            return []

        chunks: list[RetrievedChunk] = []
        for intent in intents:
            result = await self.vector_store.search(
                context.query,
                top_k=intent.top_k or context.top_k,
                kb_id=intent.kb_id,
            )
            for chunk in result:
                chunks.append(
                    RetrievedChunk(
                        id=chunk.id,
                        content=chunk.content,
                        score=chunk.score * max(intent.confidence, 0.1),
                        metadata={
                            **chunk.metadata,
                            "intentId": intent.intent_id,
                            "intentCode": intent.intent_code,
                            "intentName": intent.name,
                            "channel": self.name,
                        },
                    ),
                )
        return chunks
