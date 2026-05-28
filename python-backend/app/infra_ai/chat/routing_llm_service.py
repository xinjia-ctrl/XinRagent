from collections.abc import AsyncIterator, Callable, Sequence

from app.infra_ai.chat.base import ChatChunk, ChatClient, ChatRequest, ChatResponse
from app.infra_ai.chat.openai_style_client import OpenAIStyleChatClient
from app.infra_ai.model_target import ModelTarget
from app.infra_ai.routing_executor import ModelRoutingExecutor

ChatClientFactory = Callable[[ModelTarget], ChatClient]


class RoutingLLMService:
    def __init__(
        self,
        targets: Sequence[ModelTarget],
        executor: ModelRoutingExecutor | None = None,
        client_factory: ChatClientFactory = OpenAIStyleChatClient,
    ) -> None:
        self.targets = list(targets)
        self.executor = executor or ModelRoutingExecutor()
        self.client_factory = client_factory

    async def complete(self, request: ChatRequest) -> ChatResponse:
        async def operation(target: ModelTarget) -> ChatResponse:
            client = self.client_factory(target)
            routed_request = self._with_target_model(request, target)
            return await client.complete(routed_request)

        return await self.executor.execute(self.targets, operation)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        response = await self.complete(request)
        yield ChatChunk(delta=response.content, finish_reason="stop", raw=response.raw)

    @staticmethod
    def _with_target_model(request: ChatRequest, target: ModelTarget) -> ChatRequest:
        return ChatRequest(
            messages=request.messages,
            model=target.model or request.model,
            temperature=request.temperature,
            stream=request.stream,
            extra_body=request.extra_body,
        )
