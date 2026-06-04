from dataclasses import dataclass, field

from app.infra_ai.chat import ChatMessage
from app.rag.intent import IntentResolution
from app.mcp import MCPResponse
from app.rag.rewrite import RewriteResult
from app.rag.retrieve import RetrievedChunk


@dataclass
class StreamChatContext:
    question: str
    conversation_id: str | None
    task_id: str
    user_id: str | None = None
    deep_thinking: bool = False
    history: list[ChatMessage] = field(default_factory=list)
    rewrite_result: RewriteResult | None = None
    intent_resolution: IntentResolution | None = None
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    mcp_responses: list[MCPResponse] = field(default_factory=list)
    assistant_message_id: str | None = None
    title: str | None = None
