import pytest

from app.core.exceptions import RagentException
from app.infra_ai.chat import ChatChunk, ChatRequest
from app.infra_ai.chat.routing_llm_service import RoutingLLMService
from app.infra_ai.health_store import ModelHealthState, ModelHealthStore
from app.infra_ai.model_target import ModelTarget
from app.infra_ai.routing_executor import ModelRoutingExecutor


def target(name: str, priority: int) -> ModelTarget:
    return ModelTarget(name=name, base_url="http://example.test", model=name, priority=priority)


@pytest.mark.asyncio
async def test_routing_executor_uses_priority_order() -> None:
    called: list[str] = []
    executor = ModelRoutingExecutor()

    async def operation(model_target: ModelTarget) -> str:
        called.append(model_target.name)
        return model_target.name

    result = await executor.execute([target("slow", 30), target("fast", 10)], operation)

    assert result == "fast"
    assert called == ["fast"]


@pytest.mark.asyncio
async def test_routing_executor_falls_back_after_failure() -> None:
    called: list[str] = []
    executor = ModelRoutingExecutor()

    async def operation(model_target: ModelTarget) -> str:
        called.append(model_target.name)
        if model_target.name == "primary":
            raise RuntimeError("primary failed")
        return "secondary-ok"

    result = await executor.execute([target("primary", 10), target("secondary", 20)], operation)

    assert result == "secondary-ok"
    assert called == ["primary", "secondary"]
    assert executor.health_store.get("primary").failure_count == 1
    assert executor.health_store.get("secondary").state == ModelHealthState.CLOSED


@pytest.mark.asyncio
async def test_routing_executor_skips_open_target() -> None:
    health_store = ModelHealthStore(failure_threshold=1, cooldown_seconds=60)
    health_store.mark_failure("primary")
    executor = ModelRoutingExecutor(health_store)
    called: list[str] = []

    async def operation(model_target: ModelTarget) -> str:
        called.append(model_target.name)
        return model_target.name

    result = await executor.execute([target("primary", 10), target("secondary", 20)], operation)

    assert result == "secondary"
    assert called == ["secondary"]


@pytest.mark.asyncio
async def test_routing_executor_raises_when_all_targets_fail() -> None:
    executor = ModelRoutingExecutor(ModelHealthStore(failure_threshold=1))

    async def operation(_: ModelTarget) -> str:
        raise RuntimeError("remote failed")

    with pytest.raises(RagentException) as exc_info:
        await executor.execute([target("primary", 10), target("secondary", 20)], operation)

    assert exc_info.value.code == "AI_REMOTE_ERROR"
    assert executor.health_store.get("primary").state == ModelHealthState.OPEN
    assert executor.health_store.get("secondary").state == ModelHealthState.OPEN


@pytest.mark.asyncio
async def test_routing_llm_service_stream_uses_client_stream_and_fallback() -> None:
    calls: list[str] = []

    class FakeClient:
        def __init__(self, model_target: ModelTarget) -> None:
            self.model_target = model_target

        async def complete(self, _: ChatRequest):
            raise AssertionError("stream should not call complete")

        async def stream(self, _: ChatRequest):
            calls.append(self.model_target.name)
            if self.model_target.name == "primary":
                raise RuntimeError("primary stream failed")
            yield ChatChunk(delta="真")
            yield ChatChunk(delta="流式")

    service = RoutingLLMService(
        [target("primary", 10), target("secondary", 20)],
        client_factory=FakeClient,
    )

    chunks = [
        chunk.delta
        async for chunk in service.stream(ChatRequest(messages=[], model="model", stream=True))
    ]

    assert calls == ["primary", "secondary"]
    assert chunks == ["真", "流式"]


@pytest.mark.asyncio
async def test_routing_llm_service_prefers_requested_model_target() -> None:
    calls: list[str] = []

    class FakeClient:
        def __init__(self, model_target: ModelTarget) -> None:
            self.model_target = model_target

        async def complete(self, _: ChatRequest):
            raise AssertionError("stream should not call complete")

        async def stream(self, _: ChatRequest):
            calls.append(self.model_target.name)
            yield ChatChunk(delta=self.model_target.name)

    service = RoutingLLMService(
        [target("default", 0), target("thinking", 10)],
        client_factory=FakeClient,
    )

    chunks = [
        chunk.delta
        async for chunk in service.stream(ChatRequest(messages=[], model="thinking", stream=True))
    ]

    assert calls == ["thinking"]
    assert chunks == ["thinking"]
