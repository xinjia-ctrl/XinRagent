from collections.abc import AsyncIterator

from app.core.config import settings
from app.infra_ai.chat import ChatRequest, RoutingLLMService
from app.rag.pipeline.stream_chat_context import StreamChatContext
from app.rag.prompt import PromptService
from app.rag.retrieve.retrieval_engine import RetrievalEngine


class StreamChatPipeline:
    def __init__(
        self,
        llm_service: RoutingLLMService,
        retrieval_engine: RetrievalEngine | None = None,
        prompt_service: PromptService | None = None,
    ) -> None:
        self.llm_service = llm_service
        self.retrieval_engine = retrieval_engine
        self.prompt_service = prompt_service or PromptService()

    async def execute(self, context: StreamChatContext) -> AsyncIterator[str]:
        chunks = []
        if self.retrieval_engine is not None:
            chunks = await self.retrieval_engine.retrieve(
                query=context.question,
                conversation_id=context.conversation_id,
                user_id=context.user_id,
            )

        request = ChatRequest(
            messages=self.prompt_service.build_messages(context.question, chunks),
            model=settings.ai_chat_default_model,
            stream=True,
        )
        async for chunk in self.llm_service.stream(request):
            if chunk.delta:
                yield chunk.delta
