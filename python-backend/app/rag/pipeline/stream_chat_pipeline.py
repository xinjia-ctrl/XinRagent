from collections.abc import AsyncIterator

from app.core.config import settings
from app.infra_ai.chat import ChatMessage, ChatRequest, RoutingLLMService
from app.rag.pipeline.stream_chat_context import StreamChatContext


class StreamChatPipeline:
    def __init__(self, llm_service: RoutingLLMService) -> None:
        self.llm_service = llm_service

    async def execute(self, context: StreamChatContext) -> AsyncIterator[str]:
        request = ChatRequest(
            messages=[
                ChatMessage(role="system", content="你是 Ragent Python 后端的 AI 助手。"),
                ChatMessage(role="user", content=context.question),
            ],
            model=settings.ai_chat_default_model,
            stream=True,
        )
        async for chunk in self.llm_service.stream(request):
            if chunk.delta:
                yield chunk.delta
