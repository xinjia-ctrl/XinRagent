from dataclasses import dataclass, field

from app.core.config import settings
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
    ) -> None:
        self.multi_channel_engine = multi_channel_engine
        self.mcp_service = mcp_service

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
        context = SearchContext(
            query=query,
            top_k=top_k or settings.rag_default_top_k,
            original_query=original_query,
            conversation_id=conversation_id,
            user_id=user_id,
            intents=intents,
        )
        chunks = await self.multi_channel_engine.retrieve_knowledge_channels(context)
        mcp_responses = []
        if self.mcp_service is not None:
            mcp_responses = await self.mcp_service.execute_for_intents(
                question=query,
                intents=[intent for intent in intents or [] if intent.is_mcp],
                user_id=user_id,
            )
        return RetrievalResult(chunks=chunks, mcp_responses=mcp_responses)
