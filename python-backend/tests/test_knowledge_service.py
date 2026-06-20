from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.core.config import settings
from app.schemas.knowledge import KnowledgeBaseCreateRequest, KnowledgeBaseUpdateRequest
from app.services.knowledge_service import KnowledgeService


@pytest.mark.asyncio
async def test_knowledge_service_creates_vector_collection() -> None:
    session = AsyncMock()
    vector_space_manager = AsyncMock()
    service = KnowledgeService(session, vector_space_manager)

    response = await service.create_knowledge_base(
        KnowledgeBaseCreateRequest(name="默认知识库", collectionName="kb_docs"),
        user_id="user-1",
    )

    assert response.collectionName == "kb_docs"
    vector_space_manager.ensure_collection.assert_awaited_once_with(
        "kb_docs",
        settings.rag_default_dimension,
    )
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_knowledge_service_updates_vector_collection_when_name_changes() -> None:
    session = AsyncMock()
    vector_space_manager = AsyncMock()
    service = KnowledgeService(session, vector_space_manager)
    service._get_knowledge_base = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "id": "kb-1",
            "name": "旧知识库",
            "embedding_model": "embed",
            "collection_name": "kb_old",
            "created_by": "user-1",
            "create_time": None,
            "update_time": None,
        },
    )

    response = await service.update_knowledge_base(
        "kb-1",
        KnowledgeBaseUpdateRequest(collectionName="kb_new"),
        user_id="user-1",
    )

    assert response.collectionName == "kb_new"
    vector_space_manager.ensure_collection.assert_awaited_once_with(
        "kb_new",
        settings.rag_default_dimension,
    )


@pytest.mark.asyncio
async def test_knowledge_service_drops_vector_collection_when_deleted() -> None:
    session = AsyncMock()
    session.execute.return_value = SimpleNamespace(rowcount=1)
    vector_space_manager = AsyncMock()
    service = KnowledgeService(session, vector_space_manager)
    service._get_knowledge_base = AsyncMock(  # type: ignore[method-assign]
        return_value={"collection_name": "kb_docs"},
    )

    response = await service.delete_knowledge_base("kb-1", user_id="user-1")

    assert response.deleted is True
    vector_space_manager.drop_collection.assert_awaited_once_with("kb_docs")
