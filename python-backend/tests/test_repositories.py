from unittest.mock import AsyncMock

import pytest
from sqlalchemy.sql import Select

from app.models import Conversation, User
from app.repositories import (
    ConversationRepository,
    KnowledgeBaseRepository,
    UserRepository,
)
from app.repositories.base import BaseRepository


def test_base_repository_builds_select_for_model() -> None:
    repository = BaseRepository(AsyncMock(), User)

    assert isinstance(repository.select(), Select)


@pytest.mark.asyncio
async def test_user_repository_get_by_username_returns_scalar_result() -> None:
    session = AsyncMock()
    expected_user = User(username="admin", password="secret")
    session.scalar.return_value = expected_user
    repository = UserRepository(session)

    user = await repository.get_by_username("admin")

    assert user is expected_user
    session.scalar.assert_awaited_once()


def test_repository_classes_bind_expected_models() -> None:
    session = AsyncMock()

    assert ConversationRepository(session).model is Conversation
    assert KnowledgeBaseRepository(session).model.__tablename__ == "t_knowledge_base"
