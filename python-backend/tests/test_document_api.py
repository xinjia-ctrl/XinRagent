from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.documents import get_document_service
from app.main import create_app
from app.models import User
from app.schemas.document import (
    KnowledgeChunkPageResponse,
    KnowledgeChunkResponse,
    KnowledgeDocumentChunkLogPageResponse,
    KnowledgeDocumentChunkLogResponse,
    KnowledgeDocumentPageResponse,
    KnowledgeDocumentResponse,
    KnowledgeDocumentSearchItem,
)


async def override_current_user() -> User:
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    return user


def create_document_client(service: object) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_document_service] = lambda: service
    return TestClient(app)


def test_document_page_search_and_detail_api_match_frontend_shape() -> None:
    service = AsyncMock()
    service.list_documents.return_value = KnowledgeDocumentPageResponse(
        records=[
            KnowledgeDocumentResponse(
                id="doc-1",
                kbId="kb-1",
                docName="intro.md",
                fileUrl="storage/intro.md",
                fileType="md",
                fileSize=12,
                status="indexed",
                chunkCount=2,
                enabled=True,
            ),
        ],
        total=1,
        size=5,
        current=2,
        pages=1,
    )
    service.search_documents.return_value = [
        KnowledgeDocumentSearchItem(id="doc-1", kbId="kb-1", docName="intro.md", kbName="默认知识库"),
    ]
    service.get_document.return_value = KnowledgeDocumentResponse(
        id="doc-1",
        kbId="kb-1",
        docName="intro.md",
        fileUrl="storage/intro.md",
        fileType="md",
        status="indexed",
        chunkCount=2,
    )
    client = create_document_client(service)

    page_response = client.get(
        "/api/ragent/knowledge-base/kb-1/docs?current=2&size=5&status=indexed&keyword=intro",
    )
    search_response = client.get("/api/ragent/knowledge-base/docs/search?keyword=intro&limit=3")
    detail_response = client.get("/api/ragent/knowledge-base/docs/doc-1")

    assert page_response.status_code == 200
    assert page_response.json()["data"]["records"][0]["docName"] == "intro.md"
    assert page_response.json()["data"]["records"][0]["chunkCount"] == 2
    assert search_response.json()["data"][0]["kbName"] == "默认知识库"
    assert detail_response.json()["data"]["fileUrl"] == "storage/intro.md"
    service.list_documents.assert_awaited_once_with(
        "kb-1",
        current=2,
        size=5,
        status="indexed",
        keyword="intro",
    )
    service.search_documents.assert_awaited_once_with("intro", limit=3)
    service.get_document.assert_awaited_once_with("doc-1")


def test_document_write_apis_delegate_to_service() -> None:
    service = AsyncMock()
    client = create_document_client(service)

    update_response = client.put(
        "/api/ragent/knowledge-base/docs/doc-1",
        json={
            "docName": "guide.md",
            "processMode": "chunk",
            "chunkStrategy": "fixed_size",
            "chunkConfig": "{\"chunkSize\":800}",
        },
    )
    chunk_response = client.post("/api/ragent/knowledge-base/docs/doc-1/chunk")
    enable_response = client.patch("/api/ragent/knowledge-base/docs/doc-1/enable?value=false")
    delete_response = client.delete("/api/ragent/knowledge-base/docs/doc-1")

    assert update_response.json()["data"] is None
    assert chunk_response.json()["data"] is None
    assert enable_response.json()["data"] is None
    assert delete_response.json()["data"] is None
    update_request = service.update_document.await_args.args[1]
    assert update_request.doc_name == "guide.md"
    assert update_request.chunk_strategy == "fixed_size"
    service.start_document_chunk.assert_awaited_once_with("doc-1", "1")
    service.enable_document.assert_awaited_once_with("doc-1", False, "1")
    service.delete_document.assert_awaited_once_with("doc-1", "1")


def test_chunk_management_apis_match_frontend_contract() -> None:
    service = AsyncMock()
    service.list_chunks.return_value = KnowledgeChunkPageResponse(
        records=[
            KnowledgeChunkResponse(
                id="chunk-1",
                kbId="kb-1",
                docId="doc-1",
                chunkIndex=0,
                content="Ragent 知识片段",
                contentHash="hash",
                charCount=10,
                tokenCount=2,
                enabled=1,
            ),
        ],
        total=1,
        size=10,
        current=1,
        pages=1,
    )
    service.create_chunk.return_value = KnowledgeChunkResponse(
        id="chunk-new",
        kbId="kb-1",
        docId="doc-1",
        chunkIndex=1,
        content="新的片段",
        enabled=1,
    )
    service.list_chunk_logs.return_value = KnowledgeDocumentChunkLogPageResponse(
        records=[
            KnowledgeDocumentChunkLogResponse(
                id="log-1",
                docId="doc-1",
                status="indexed",
                processMode="chunk",
                chunkCount=2,
            ),
        ],
        total=1,
        size=10,
        current=1,
        pages=1,
    )
    client = create_document_client(service)

    page_response = client.get("/api/ragent/knowledge-base/docs/doc-1/chunks?enabled=1")
    create_response = client.post(
        "/api/ragent/knowledge-base/docs/doc-1/chunks",
        json={"content": "新的片段", "index": 1, "chunkId": "chunk-new"},
    )
    update_response = client.put(
        "/api/ragent/knowledge-base/docs/doc-1/chunks/chunk-1",
        json={"content": "更新后的片段"},
    )
    delete_response = client.delete("/api/ragent/knowledge-base/docs/doc-1/chunks/chunk-1")
    enable_response = client.patch("/api/ragent/knowledge-base/docs/doc-1/chunks/chunk-1/enable?value=false")
    batch_response = client.patch(
        "/api/ragent/knowledge-base/docs/doc-1/chunks/batch-enable?value=true",
        json={"chunkIds": ["chunk-1", "chunk-2"]},
    )
    logs_response = client.get("/api/ragent/knowledge-base/docs/doc-1/chunk-logs")

    assert page_response.json()["data"]["records"][0]["contentHash"] == "hash"
    assert create_response.json()["data"]["id"] == "chunk-new"
    assert update_response.json()["data"] is None
    assert delete_response.json()["data"] is None
    assert enable_response.json()["data"] is None
    assert batch_response.json()["data"] is None
    assert logs_response.json()["data"]["records"][0]["processMode"] == "chunk"
    create_request = service.create_chunk.await_args.args[1]
    update_request = service.update_chunk.await_args.args[2]
    batch_request = service.batch_enable_chunks.await_args.args[1]
    assert create_request.chunkId == "chunk-new"
    assert update_request.content == "更新后的片段"
    assert batch_request.chunkIds == ["chunk-1", "chunk-2"]
    service.list_chunks.assert_awaited_once_with("doc-1", current=1, size=10, enabled=1)
    service.enable_chunk.assert_awaited_once_with("doc-1", "chunk-1", False, "1")
