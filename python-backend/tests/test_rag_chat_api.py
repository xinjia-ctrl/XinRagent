import json
from collections.abc import AsyncIterator
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.chat import get_llm_service, get_retrieval_engine, get_trace_service
from app.infra_ai.chat import ChatChunk, ChatRequest
from app.main import create_app
from app.models import User


class FakeLLMService:
    async def stream(self, _: ChatRequest) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(delta="你好")
        yield ChatChunk(delta="，Ragent")


class EmptyRetrievalEngine:
    async def retrieve(self, **_: object) -> list:
        return []


def authenticated_user() -> User:
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    return user


async def override_current_user() -> User:
    return authenticated_user()


def create_rag_test_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_llm_service] = lambda: FakeLLMService()
    app.dependency_overrides[get_retrieval_engine] = lambda: EmptyRetrievalEngine()
    app.dependency_overrides[get_trace_service] = lambda: None
    return TestClient(app)


def parse_sse_events(content: str) -> list[dict]:
    events = []
    for block in content.strip().split("\n\n"):
        data_line = next(line for line in block.splitlines() if line.startswith("data: "))
        events.append(json.loads(data_line.removeprefix("data: ")))
    return events


def test_stream_chat_api_returns_sse_events() -> None:
    client = create_rag_test_client()

    with client.stream(
        "GET",
        "/api/ragent/rag/v3/chat",
        params={"question": "你好", "conversationId": "conv-1"},
    ) as response:
        content = response.read().decode("utf-8")

    events = parse_sse_events(content)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert [event["type"] for event in events] == ["start", "delta", "delta", "complete"]
    assert "".join(event.get("content", "") for event in events) == "你好，Ragent"
    assert all(event["conversationId"] == "conv-1" for event in events)
    assert all(event["taskId"] for event in events)


def test_stop_chat_api_cancels_registered_task() -> None:
    client = create_rag_test_client()

    with patch("app.api.v1.chat.stream_task_manager.cancel", return_value=True) as cancel:
        response = client.post("/api/ragent/rag/v3/stop", json={"task_id": "task-to-stop"})

    assert response.status_code == 200
    assert response.json() == {"code": "0", "message": "success", "data": {"stopped": True}}
    cancel.assert_called_once_with("task-to-stop")


def test_stream_chat_api_requires_authorization() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/ragent/rag/v3/chat", params={"question": "你好"})

    assert response.status_code == 401
    assert response.json()["code"] == "40100"
