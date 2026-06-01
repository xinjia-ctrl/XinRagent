from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.documents import get_document_service
from app.api.v1.knowledge_base import get_knowledge_service
from app.api.v1.traces import get_trace_service
from app.main import create_app
from app.models import User
from app.schemas.document import KnowledgeChunkResponse, KnowledgeDocumentResponse
from app.schemas.knowledge import (
    ChunkStrategyOption,
    DeleteResponse,
    KnowledgeBasePageResponse,
    KnowledgeBaseResponse,
)
from app.schemas.trace import TraceDetailResponse, TraceNodeResponse, TraceRunResponse


class FakeKnowledgeService:
    async def list_knowledge_bases(
        self,
        current: int = 1,
        size: int = 10,
        name: str | None = None,
    ) -> KnowledgeBasePageResponse:
        return KnowledgeBasePageResponse(
            records=[
                KnowledgeBaseResponse(
                    id="kb-1",
                    name=name or "默认知识库",
                    embeddingModel="qwen-emb-8b",
                    collectionName="kb_default",
                    createdBy="1",
                    documentCount=2,
                ),
            ],
            total=1,
            size=size,
            current=current,
            pages=1,
        )

    async def get_knowledge_base(self, kb_id: str) -> KnowledgeBaseResponse:
        return KnowledgeBaseResponse(
            id=kb_id,
            name="默认知识库",
            embeddingModel="qwen-emb-8b",
            collectionName="kb_default",
            createdBy="1",
            documentCount=2,
        )

    async def list_chunk_strategies(self) -> list[ChunkStrategyOption]:
        return [
            ChunkStrategyOption(
                value="fixed_size",
                label="固定长度分块",
                defaultConfig={"chunkSize": 800, "overlap": 100},
            ),
        ]

    async def create_knowledge_base(self, request, user_id: str) -> KnowledgeBaseResponse:
        return KnowledgeBaseResponse(
            id="kb-new",
            name=request.name,
            embeddingModel=request.embedding_model,
            collectionName=request.collection_name or "kb_kb-new",
            createdBy=user_id,
        )

    async def update_knowledge_base(self, kb_id: str, request, user_id: str) -> KnowledgeBaseResponse:
        return KnowledgeBaseResponse(
            id=kb_id,
            name=request.name or "更新后的知识库",
            embeddingModel=request.embedding_model or "qwen-emb-8b",
            collectionName=request.collection_name or "kb_default",
            createdBy=user_id,
        )

    async def delete_knowledge_base(self, _: str, __: str) -> DeleteResponse:
        return DeleteResponse(deleted=True)


class FakeDocumentService:
    async def list_documents(self, kb_id: str) -> list[KnowledgeDocumentResponse]:
        return [
            KnowledgeDocumentResponse(
                id="doc-1",
                kb_id=kb_id,
                doc_name="intro.md",
                file_url="storage/intro.md",
                file_type="md",
                file_size=12,
                status="indexed",
                chunk_count=1,
            ),
        ]

    async def get_document(self, doc_id: str) -> KnowledgeDocumentResponse:
        return KnowledgeDocumentResponse(
            id=doc_id,
            kb_id="kb-1",
            doc_name="intro.md",
            file_url="storage/intro.md",
            file_type="md",
            file_size=12,
            status="indexed",
            chunk_count=1,
        )

    async def list_chunks(self, doc_id: str) -> list[KnowledgeChunkResponse]:
        return [
            KnowledgeChunkResponse(
                id="chunk-1",
                kb_id="kb-1",
                doc_id=doc_id,
                chunk_index=0,
                content="Ragent 知识片段",
                char_count=10,
                token_count=2,
            ),
        ]


class FakeTraceService:
    async def list_runs(self, limit: int = 50) -> list[TraceRunResponse]:
        return [
            TraceRunResponse(
                trace_id="trace-1",
                trace_name="rag_chat",
                conversation_id="conv-1",
                task_id="task-1",
                user_id="1",
                status="SUCCESS",
                duration_ms=12,
            ),
        ][:limit]

    async def get_run_detail(self, trace_id: str) -> TraceDetailResponse:
        return TraceDetailResponse(
            run=TraceRunResponse(trace_id=trace_id, status="SUCCESS"),
            nodes=[
                TraceNodeResponse(
                    node_id="node-1",
                    node_name="stream_chat_pipeline",
                    node_type="PIPELINE",
                    status="SUCCESS",
                    duration_ms=12,
                ),
            ],
        )


async def override_current_user() -> User:
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    return user


def create_management_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_knowledge_service] = lambda: FakeKnowledgeService()
    app.dependency_overrides[get_document_service] = lambda: FakeDocumentService()
    app.dependency_overrides[get_trace_service] = lambda: FakeTraceService()
    return TestClient(app)


def test_knowledge_base_management_api() -> None:
    client = create_management_client()

    list_response = client.get("/api/ragent/knowledge-base")
    detail_response = client.get("/api/ragent/knowledge-base/kb-1")
    create_response = client.post("/api/ragent/knowledge-base", json={"name": "新知识库"})
    update_response = client.put("/api/ragent/knowledge-base/kb-1", json={"name": "更新后的知识库"})
    strategies_response = client.get("/api/ragent/knowledge-base/chunk-strategies")
    delete_response = client.delete("/api/ragent/knowledge-base/kb-1")

    assert list_response.status_code == 200
    assert list_response.json()["data"]["records"][0]["id"] == "kb-1"
    assert list_response.json()["data"]["records"][0]["embeddingModel"] == "qwen-emb-8b"
    assert detail_response.json()["data"]["collectionName"] == "kb_default"
    assert create_response.json()["data"] == "kb-new"
    assert update_response.json()["data"] is None
    assert strategies_response.json()["data"][0]["value"] == "fixed_size"
    assert delete_response.json()["data"] == {"deleted": True}


def test_document_and_chunk_query_api() -> None:
    client = create_management_client()

    docs_response = client.get("/api/ragent/knowledge-base/kb-1/docs")
    doc_response = client.get("/api/ragent/knowledge-base/docs/doc-1")
    chunks_response = client.get("/api/ragent/knowledge-base/docs/doc-1/chunks")

    assert docs_response.status_code == 200
    assert docs_response.json()["data"][0]["doc_name"] == "intro.md"
    assert doc_response.json()["data"]["id"] == "doc-1"
    assert chunks_response.json()["data"][0]["content"] == "Ragent 知识片段"


def test_trace_query_api() -> None:
    client = create_management_client()

    runs_response = client.get("/api/ragent/rag/traces/runs")
    detail_response = client.get("/api/ragent/rag/traces/runs/trace-1")

    assert runs_response.status_code == 200
    assert runs_response.json()["data"][0]["trace_id"] == "trace-1"
    assert detail_response.json()["data"]["nodes"][0]["node_name"] == "stream_chat_pipeline"
