import json
from collections.abc import AsyncIterator
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.chat import (
    get_chat_queue_limiter,
    get_intent_resolver,
    get_llm_service,
    get_memory_service,
    get_query_rewrite_service,
    get_retrieval_engine,
    get_trace_service,
)
from app.infra_ai.chat import ChatChunk, ChatRequest
from app.main import create_app
from app.models import User
from app.rag.intent import IntentResolution
from app.rag.rate_limit import ChatQueueLimiter
from app.rag.rewrite import RewriteResult


class RegressionLLMService:
    async def stream(self, _: ChatRequest) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(delta="pong")


class RegressionRetrievalEngine:
    async def retrieve(self, **_: object) -> list:
        return []


class NoopMemoryService:
    async def load_history(self, *_: object) -> list:
        return []

    async def append_user_message(self, *_: object) -> None:
        return None

    async def append_assistant_message(self, *_: object) -> None:
        return None


class NoopRewriteService:
    async def rewrite_with_split(self, question: str, *_: object) -> RewriteResult:
        return RewriteResult(question, question, [question])


class NoopIntentResolver:
    async def resolve(self, _: RewriteResult) -> IntentResolution:
        return IntentResolution(matches=[])


async def override_current_user() -> User:
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    return user


def create_regression_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_llm_service] = lambda: RegressionLLMService()
    app.dependency_overrides[get_retrieval_engine] = lambda: RegressionRetrievalEngine()
    app.dependency_overrides[get_memory_service] = lambda: NoopMemoryService()
    app.dependency_overrides[get_query_rewrite_service] = lambda: NoopRewriteService()
    app.dependency_overrides[get_intent_resolver] = lambda: NoopIntentResolver()
    app.dependency_overrides[get_trace_service] = lambda: None
    app.dependency_overrides[get_chat_queue_limiter] = lambda: ChatQueueLimiter.disabled()
    return TestClient(app)


def parse_sse_events(content: str) -> list[dict]:
    events = []
    for block in content.strip().split("\n\n"):
        event_line = next(line for line in block.splitlines() if line.startswith("event: "))
        data_line = next(line for line in block.splitlines() if line.startswith("data: "))
        events.append(
            {
                "event": event_line.removeprefix("event: "),
                "data": json.loads(data_line.removeprefix("data: ")),
            },
        )
    return events


def test_core_backend_contract_regression() -> None:
    client = create_regression_client()

    health_response = client.get("/health")
    with client.stream(
        "POST",
        "/api/ragent/rag/v3/chat",
        json={"question": "ping", "conversationId": "conv-10", "deepThinking": True},
    ) as chat_response:
        chat_content = chat_response.read().decode("utf-8")
    chat_events = parse_sse_events(chat_content)

    with patch("app.api.v1.chat.stream_task_manager.cancel", return_value=True) as cancel:
        stop_response = client.post(
            "/api/ragent/rag/v3/stop",
            json={"taskId": chat_events[0]["data"]["taskId"]},
        )

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert chat_response.status_code == 200
    assert [event["event"] for event in chat_events] == ["meta", "message", "finish", "done"]
    assert chat_events[0]["data"]["conversationId"] == "conv-10"
    assert chat_events[1]["data"]["delta"] == "pong"
    assert stop_response.json() == {"code": "0", "message": "success", "data": {"stopped": True}}
    cancel.assert_called_once_with(chat_events[0]["data"]["taskId"])
