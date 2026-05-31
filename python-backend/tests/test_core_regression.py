import json
from collections.abc import AsyncIterator
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.chat import get_llm_service, get_retrieval_engine, get_trace_service
from app.infra_ai.chat import ChatChunk, ChatRequest
from app.main import create_app
from app.models import User


class RegressionLLMService:
    async def stream(self, _: ChatRequest) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(delta="pong")


class RegressionRetrievalEngine:
    async def retrieve(self, **_: object) -> list:
        return []


async def override_current_user() -> User:
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    return user


def create_regression_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_llm_service] = lambda: RegressionLLMService()
    app.dependency_overrides[get_retrieval_engine] = lambda: RegressionRetrievalEngine()
    app.dependency_overrides[get_trace_service] = lambda: None
    return TestClient(app)


def parse_sse_events(content: str) -> list[dict]:
    events = []
    for block in content.strip().split("\n\n"):
        data_line = next(line for line in block.splitlines() if line.startswith("data: "))
        events.append(json.loads(data_line.removeprefix("data: ")))
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
            json={"taskId": chat_events[0]["taskId"]},
        )

    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}
    assert chat_response.status_code == 200
    assert [event["type"] for event in chat_events] == ["start", "delta", "complete"]
    assert chat_events[0]["conversationId"] == "conv-10"
    assert chat_events[1]["content"] == "pong"
    assert stop_response.json() == {"code": "0", "message": "success", "data": {"stopped": True}}
    cancel.assert_called_once_with(chat_events[0]["taskId"])
