from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.knowledge_base import get_knowledge_service
from app.main import create_app
from app.models import User
from app.schemas.knowledge import (
    ChunkStrategyOption,
    DeleteResponse,
    KnowledgeBasePageResponse,
    KnowledgeBaseResponse,
)


async def override_current_user() -> User:
    return User(id="1", username="admin", password="secret", role="admin", status=1)


def create_knowledge_test_client(service: object) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_knowledge_service] = lambda: service
    return TestClient(app)


def test_knowledge_base_page_and_detail_api_match_frontend_shape() -> None:
    service = AsyncMock()
    service.list_knowledge_bases.return_value = KnowledgeBasePageResponse(
        records=[
            KnowledgeBaseResponse(
                id="kb-1",
                name="默认知识库",
                embeddingModel="qwen-emb-8b",
                collectionName="kb_default",
                createdBy="1",
                documentCount=3,
            ),
        ],
        total=1,
        size=10,
        current=1,
        pages=1,
    )
    service.get_knowledge_base.return_value = KnowledgeBaseResponse(
        id="kb-1",
        name="默认知识库",
        embeddingModel="qwen-emb-8b",
        collectionName="kb_default",
        createdBy="1",
        documentCount=3,
    )
    client = create_knowledge_test_client(service)

    page_response = client.get("/api/ragent/knowledge-base?current=1&size=10&name=默认")
    detail_response = client.get("/api/ragent/knowledge-base/kb-1")

    assert page_response.status_code == 200
    assert page_response.json()["data"]["records"][0]["documentCount"] == 3
    assert detail_response.json()["data"]["embeddingModel"] == "qwen-emb-8b"
    service.list_knowledge_bases.assert_awaited_once_with(current=1, size=10, name="默认")
    service.get_knowledge_base.assert_awaited_once_with("kb-1")


def test_knowledge_base_create_update_delete_api_match_frontend_contract() -> None:
    service = AsyncMock()
    service.create_knowledge_base.return_value = KnowledgeBaseResponse(
        id="kb-new",
        name="新知识库",
        embeddingModel="qwen-emb-8b",
        collectionName="kb_kb-new",
        createdBy="1",
    )
    service.update_knowledge_base.return_value = KnowledgeBaseResponse(
        id="kb-new",
        name="更新后的知识库",
        embeddingModel="qwen-emb-8b",
        collectionName="kb_kb-new",
        createdBy="1",
    )
    service.delete_knowledge_base.return_value = DeleteResponse(deleted=True)
    client = create_knowledge_test_client(service)

    create_response = client.post(
        "/api/ragent/knowledge-base",
        json={"name": "新知识库", "embeddingModel": "qwen-emb-8b"},
    )
    update_response = client.put(
        "/api/ragent/knowledge-base/kb-new",
        json={"name": "更新后的知识库", "embeddingModel": "qwen-emb-8b"},
    )
    delete_response = client.delete("/api/ragent/knowledge-base/kb-new")

    assert create_response.json()["data"] == "kb-new"
    assert update_response.json()["data"] is None
    assert delete_response.json()["data"] == {"deleted": True}


def test_chunk_strategies_api_returns_options() -> None:
    service = AsyncMock()
    service.list_chunk_strategies.return_value = [
        ChunkStrategyOption(
            value="fixed_size",
            label="固定长度分块",
            defaultConfig={"chunkSize": 800, "overlap": 100},
        ),
    ]
    client = create_knowledge_test_client(service)

    response = client.get("/api/ragent/knowledge-base/chunk-strategies")

    assert response.status_code == 200
    assert response.json()["data"] == [
        {
            "value": "fixed_size",
            "label": "固定长度分块",
            "defaultConfig": {"chunkSize": 800, "overlap": 100},
        },
    ]


def test_knowledge_base_response_accepts_python_and_frontend_field_names() -> None:
    response = KnowledgeBaseResponse(
        id="kb-1",
        name="默认知识库",
        embedding_model="qwen-emb-8b",
        collection_name="kb_default",
        created_by="1",
        document_count=2,
    )

    assert response.embeddingModel == "qwen-emb-8b"
    assert response.collectionName == "kb_default"
    assert response.createdBy == "1"
    assert response.documentCount == 2
