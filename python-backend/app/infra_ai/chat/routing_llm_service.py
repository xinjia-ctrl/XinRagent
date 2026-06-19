from collections.abc import AsyncIterator, Callable, Sequence

from app.core.exceptions import RagentException
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

        return await self.executor.execute(self._ordered_targets(request), operation)

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        last_error: Exception | None = None
        for target in self._ordered_targets(request):
            if not self.executor.health_store.can_call(target.name):
                continue

            client = self.client_factory(target)
            routed_request = self._with_target_model(request, target)
            yielded = False
            try:
                async for chunk in client.stream(routed_request):
                    yielded = True
                    yield chunk
                self.executor.health_store.mark_success(target.name)
                return
            except Exception as exc:
                self.executor.health_store.mark_failure(target.name)
                last_error = exc
                if yielded:
                    raise
                continue

        detail = f": {last_error}" if last_error else ""
        raise RagentException(message=f"所有模型流式调用失败{detail}", code="AI_REMOTE_ERROR", status_code=502)

    @staticmethod
    def _with_target_model(request: ChatRequest, target: ModelTarget) -> ChatRequest:
        return ChatRequest(
            messages=request.messages,
            model=target.model or request.model,
            temperature=request.temperature,
            stream=request.stream,
            extra_body=request.extra_body,
        )

    def _ordered_targets(self, request: ChatRequest) -> list[ModelTarget]:
        requested_model = (request.model or "").strip()
        targets = sorted(self.targets, key=lambda item: item.priority)
        preferred = [
            target
            for target in targets
            if requested_model and requested_model in {target.name, target.model}
        ]
        if not preferred:
            return targets
        preferred_names = {target.name for target in preferred}
        return [*preferred, *[target for target in targets if target.name not in preferred_names]]
