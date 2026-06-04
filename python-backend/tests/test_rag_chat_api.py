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
from app.rag.rate_limit import ChatQueueLimiter, QueuePermit, QueueStatus
from app.rag.rewrite import RewriteResult


class FakeLLMService:
    async def stream(self, _: ChatRequest) -> AsyncIterator[ChatChunk]:
        yield ChatChunk(delta="你好")
        yield ChatChunk(delta="，Ragent")


class CountingLLMService(FakeLLMService):
    def __init__(self) -> None:
        self.called = False

    async def stream(self, request: ChatRequest) -> AsyncIterator[ChatChunk]:
        self.called = True
        async for chunk in super().stream(request):
            yield chunk


class EmptyRetrievalEngine:
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
        return RewriteResult(
            original_question=question,
            rewritten_question=question,
            sub_questions=[question],
        )


class NoopIntentResolver:
    async def resolve(self, _: RewriteResult) -> IntentResolution:
        return IntentResolution(matches=[])


class BusyQueueLimiter:
    async def acquire(self, request_id: str, on_status=None) -> QueuePermit:
        if on_status is not None:
            await on_status(
                QueueStatus(
                    request_id=request_id,
                    status="waiting",
                    position=2,
                    waiting_seconds=0.1,
                    timeout_seconds=0.2,
                    max_concurrency=1,
                ),
            )
            await on_status(
                QueueStatus(
                    request_id=request_id,
                    status="timeout",
                    position=None,
                    waiting_seconds=0.2,
                    timeout_seconds=0.2,
                    max_concurrency=1,
                ),
            )
        return QueuePermit(acquired=False, request_id=request_id, reason="timeout")


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
    assert [event["event"] for event in events] == ["meta", "message", "message", "finish", "done"]
    assert "".join(event["data"].get("delta", "") for event in events) == "你好，Ragent"
    assert events[0]["data"]["conversationId"] == "conv-1"
    assert events[0]["data"]["taskId"]
    assert events[1]["data"]["type"] == "response"


def test_stop_chat_api_cancels_registered_task() -> None:
    client = create_rag_test_client()

    with patch("app.api.v1.chat.stream_task_manager.cancel", return_value=True) as cancel:
        response = client.post("/api/ragent/rag/v3/stop", json={"task_id": "task-to-stop"})

    assert response.status_code == 200
    assert response.json() == {"code": "0", "message": "success", "data": {"stopped": True}}
    cancel.assert_called_once_with("task-to-stop")


def test_stop_chat_api_accepts_frontend_query_task_id() -> None:
    client = create_rag_test_client()

    with patch("app.api.v1.chat.stream_task_manager.cancel", return_value=True) as cancel:
        response = client.post("/api/ragent/rag/v3/stop?taskId=task-from-query")

    assert response.status_code == 200
    assert response.json() == {"code": "0", "message": "success", "data": {"stopped": True}}
    cancel.assert_called_once_with("task-from-query")


def test_stream_chat_api_generates_conversation_id_when_missing() -> None:
    client = create_rag_test_client()

    with client.stream(
        "GET",
        "/api/ragent/rag/v3/chat",
        params={"question": "你好"},
    ) as response:
        content = response.read().decode("utf-8")

    events = parse_sse_events(content)

    assert response.status_code == 200
    assert events[0]["event"] == "meta"
    assert events[0]["data"]["conversationId"]


def test_stream_chat_api_requires_authorization() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/ragent/rag/v3/chat", params={"question": "你好"})

    assert response.status_code == 401
    assert response.json()["code"] == "40100"


def test_stream_chat_api_reports_busy_when_queue_timeout() -> None:
    llm_service = CountingLLMService()
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_llm_service] = lambda: llm_service
    app.dependency_overrides[get_retrieval_engine] = lambda: EmptyRetrievalEngine()
    app.dependency_overrides[get_memory_service] = lambda: NoopMemoryService()
    app.dependency_overrides[get_query_rewrite_service] = lambda: NoopRewriteService()
    app.dependency_overrides[get_intent_resolver] = lambda: NoopIntentResolver()
    app.dependency_overrides[get_trace_service] = lambda: None
    app.dependency_overrides[get_chat_queue_limiter] = lambda: BusyQueueLimiter()
    client = TestClient(app)

    with client.stream(
        "GET",
        "/api/ragent/rag/v3/chat",
        params={"question": "你好", "conversationId": "conv-busy"},
    ) as response:
        content = response.read().decode("utf-8")

    events = parse_sse_events(content)

    assert response.status_code == 200
    assert [event["event"] for event in events] == ["meta", "queue", "queue", "message", "finish", "done"]
    assert events[1]["data"]["status"] == "waiting"
    assert events[1]["data"]["position"] == 2
    assert events[2]["data"]["status"] == "timeout"
    assert events[3]["data"]["delta"] == "系统繁忙，请稍后重试。"
    assert llm_service.called is False
