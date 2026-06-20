from collections.abc import AsyncIterator, Callable, Sequence
from time import perf_counter

from app.core.exceptions import RagentException
from app.infra_ai.chat.base import ChatChunk, ChatClient, ChatMessage, ChatRequest, ChatResponse
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
            started_at = perf_counter()
            first_token_ms: float | None = None
            try:
                async for chunk in client.stream(routed_request):
                    if first_token_ms is None:
                        first_token_ms = _elapsed_ms(started_at)
                    yielded = True
                    yield chunk
                self.executor.health_store.mark_success(
                    target.name,
                    latency_ms=_elapsed_ms(started_at),
                    first_token_ms=first_token_ms,
                )
                return
            except Exception as exc:
                self.executor.health_store.mark_failure(
                    target.name,
                    error=exc,
                    latency_ms=_elapsed_ms(started_at),
                )
                last_error = exc
                if yielded:
                    raise
                continue

        detail = f": {last_error}" if last_error else ""
        raise RagentException(message=f"所有模型流式调用失败{detail}", code="AI_REMOTE_ERROR", status_code=502)

    async def probe_first_token(self, request: ChatRequest | None = None) -> list[dict[str, object]]:
        probe_request = request or ChatRequest(
            messages=[ChatMessage(role="user", content="ping")],
            model="",
            temperature=0.0,
            stream=True,
            extra_body={"max_tokens": 1},
        )
        results = []
        for target in sorted(self.targets, key=lambda item: item.priority):
            client = self.client_factory(target)
            routed_request = self._with_target_model(probe_request, target)
            routed_request = self._with_probe_options(routed_request)
            started_at = perf_counter()
            first_token_ms: float | None = None
            try:
                async for _chunk in client.stream(routed_request):
                    first_token_ms = _elapsed_ms(started_at)
                    break
                latency_ms = _elapsed_ms(started_at)
                self.executor.health_store.mark_success(
                    target.name,
                    latency_ms=latency_ms,
                    first_token_ms=first_token_ms,
                    is_probe=True,
                )
                results.append(
                    {
                        "name": target.name,
                        "success": True,
                        "latencyMs": latency_ms,
                        "firstTokenMs": first_token_ms,
                    },
                )
            except Exception as exc:
                latency_ms = _elapsed_ms(started_at)
                self.executor.health_store.mark_failure(
                    target.name,
                    error=exc,
                    latency_ms=latency_ms,
                    is_probe=True,
                )
                results.append(
                    {
                        "name": target.name,
                        "success": False,
                        "latencyMs": latency_ms,
                        "error": str(exc),
                    },
                )
        return results

    def health_snapshot(self) -> list[dict[str, object]]:
        snapshot_by_name = {
            item["name"]: item
            for item in self.executor.health_store.snapshot()
        }
        payload = []
        for target in sorted(self.targets, key=lambda item: item.priority):
            health = snapshot_by_name.get(target.name)
            if health is None:
                self.executor.health_store.get(target.name)
                health = {
                    item["name"]: item
                    for item in self.executor.health_store.snapshot()
                }[target.name]
            payload.append(
                {
                    **health,
                    "provider": target.provider,
                    "model": target.model,
                    "priority": target.priority,
                },
            )
        return payload

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

    @staticmethod
    def _with_probe_options(request: ChatRequest) -> ChatRequest:
        extra_body = dict(request.extra_body or {})
        extra_body.setdefault("max_tokens", 1)
        return ChatRequest(
            messages=request.messages,
            model=request.model,
            temperature=0.0,
            stream=True,
            extra_body=extra_body,
        )


def _elapsed_ms(started_at: float) -> float:
    return round((perf_counter() - started_at) * 1000, 3)
