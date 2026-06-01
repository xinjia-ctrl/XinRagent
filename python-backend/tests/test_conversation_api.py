from datetime import datetime
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.db.session import get_db_session
from app.main import create_app
from app.models import User
from app.schemas.conversation import ConversationMessageResponse, ConversationResponse


async def override_current_user() -> User:
    return User(id="1", username="admin", password="secret", role="admin", status=1)


async def override_db_session() -> AsyncMock:
    return AsyncMock()


def create_conversation_test_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_db_session
    return TestClient(app)


def test_list_conversations_api_returns_frontend_shape() -> None:
    client = create_conversation_test_client()
    now = datetime(2026, 6, 1, 10, 0, 0)

    with patch("app.api.v1.conversations.ConversationService") as service_class:
        service_class.return_value.list_conversations = AsyncMock(
            return_value=[ConversationResponse(conversationId="conv-1", title="测试会话", lastTime=now)],
        )

        response = client.get("/api/ragent/conversations")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {"conversationId": "conv-1", "title": "测试会话", "lastTime": "2026-06-01T10:00:00"},
    ]
    service_class.return_value.list_conversations.assert_awaited_once_with("1")


def test_rename_and_delete_conversation_api() -> None:
    client = create_conversation_test_client()

    with patch("app.api.v1.conversations.ConversationService") as service_class:
        service = service_class.return_value
        service.rename_conversation = AsyncMock()
        service.delete_conversation = AsyncMock()

        rename_response = client.put("/api/ragent/conversations/conv-1", json={"title": "新标题"})
        delete_response = client.delete("/api/ragent/conversations/conv-1")

    assert rename_response.status_code == 200
    assert delete_response.status_code == 200
    service.rename_conversation.assert_awaited_once_with("conv-1", "1", "新标题")
    service.delete_conversation.assert_awaited_once_with("conv-1", "1")


def test_list_conversation_messages_api_returns_frontend_shape() -> None:
    client = create_conversation_test_client()
    now = datetime(2026, 6, 1, 10, 1, 0)

    with patch("app.api.v1.conversations.ConversationService") as service_class:
        service_class.return_value.list_messages = AsyncMock(
            return_value=[
                ConversationMessageResponse(
                    id="msg-1",
                    conversationId="conv-1",
                    role="assistant",
                    content="回答",
                    thinkingContent="思考",
                    thinkingDuration=2,
                    vote=1,
                    createTime=now,
                ),
            ],
        )

        response = client.get("/api/ragent/conversations/conv-1/messages")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "id": "msg-1",
            "conversationId": "conv-1",
            "role": "assistant",
            "content": "回答",
            "thinkingContent": "思考",
            "thinkingDuration": 2,
            "vote": 1,
            "createTime": "2026-06-01T10:01:00",
        },
    ]
    service_class.return_value.list_messages.assert_awaited_once_with("conv-1", "1")


def test_message_feedback_api_saves_vote() -> None:
    client = create_conversation_test_client()

    with patch("app.api.v1.conversations.ConversationService") as service_class:
        service_class.return_value.save_message_feedback = AsyncMock()

        response = client.post("/api/ragent/conversations/messages/msg-1/feedback", json={"vote": -1})

    assert response.status_code == 200
    assert response.json() == {"code": "0", "message": "success", "data": None}
    service_class.return_value.save_message_feedback.assert_awaited_once_with("msg-1", "1", -1)
