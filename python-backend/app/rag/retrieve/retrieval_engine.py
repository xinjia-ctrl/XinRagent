from dataclasses import dataclass, field

from app.core.config import settings
from app.infra_ai.rerank import RerankDocument, RerankRequest, RoutingRerankService
from app.mcp import MCPResponse, MCPService
from app.rag.intent import IntentMatch
from app.rag.retrieve import RetrievedChunk
from app.rag.retrieve.channels.base import SearchContext
from app.rag.retrieve.multi_channel_retrieval_engine import MultiChannelRetrievalEngine


@dataclass(frozen=True)
class RetrievalResult:
    chunks: list[RetrievedChunk] = field(default_factory=list)
    mcp_responses: list[MCPResponse] = field(default_factory=list)

    @property
    def mcp_context(self) -> str:
        sections = []
        for response in self.mcp_responses:
            if response.success and response.content:
                sections.append(f"工具 {response.tool_id} 返回：\n{response.content}")
            elif not response.success:
                sections.append(f"工具 {response.tool_id} 调用失败：{response.error_message}")
        return "\n\n".join(sections)


class RetrievalEngine:
    def __init__(
        self,
        multi_channel_engine: MultiChannelRetrievalEngine,
        mcp_service: MCPService | None = None,
        rerank_service: RoutingRerankService | None = None,
    ) -> None:
        self.multi_channel_engine = multi_channel_engine
        self.mcp_service = mcp_service
        self.rerank_service = rerank_service

    async def retrieve(
        self,
        query: str,
        original_query: str | None = None,
        intents: list[IntentMatch] | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
        top_k: int | None = None,
    ) -> list[RetrievedChunk]:
        result = await self.retrieve_with_context(
            query=query,
            original_query=original_query,
            intents=intents,
            conversation_id=conversation_id,
            user_id=user_id,
            top_k=top_k,
        )
        return result.chunks

    async def retrieve_with_context(
        self,
        query: str,
        original_query: str | None = None,
        intents: list[IntentMatch] | None = None,
        conversation_id: str | None = None,
        user_id: str | None = None,
        top_k: int | None = None,
    ) -> RetrievalResult:
        final_top_k = top_k or settings.rag_default_top_k
        context = SearchContext(
            query=query,
            top_k=final_top_k * 3,
            original_query=original_query,
            conversation_id=conversation_id,
            user_id=user_id,
            intents=intents,
        )
        chunks = await self.multi_channel_engine.retrieve_knowledge_channels(context)
        chunks = await self._rerank(query=query, chunks=chunks, top_k=final_top_k)
        mcp_responses = []
        if self.mcp_service is not None:
            mcp_responses = await self.mcp_service.execute_for_intents(
                question=query,
                intents=[intent for intent in intents or [] if intent.is_mcp],
                user_id=user_id,
            )
        return RetrievalResult(chunks=chunks, mcp_responses=mcp_responses)

    async def _rerank(self, *, query: str, chunks: list[RetrievedChunk], top_k: int) -> list[RetrievedChunk]:
        if not chunks:
            return []
        if self.rerank_service is None:
            return chunks[:top_k]
        try:
            response = await self.rerank_service.rerank(
                RerankRequest(
                    query=query,
                    documents=[
                        RerankDocument(
                            id=chunk.id,
                            content=chunk.content,
                            score=chunk.score,
                            metadata=chunk.metadata,
                        )
                        for chunk in chunks
                    ],
                    model=settings.ai_rerank_default_model,
                    top_n=top_k,
                ),
            )
        except Exception:
            return chunks[:top_k]
        chunk_by_id = {chunk.id: chunk for chunk in chunks}
        reranked = []
        for document in response.documents:
            source = chunk_by_id.get(document.id)
            if source is None:
                continue
            reranked.append(
                RetrievedChunk(
                    id=source.id,
                    content=source.content,
                    score=document.score,
                    metadata=source.metadata,
                ),
            )
        return reranked[:top_k] if reranked else chunks[:top_k]
