from pathlib import Path
from shutil import rmtree
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.ingestion import get_file_storage, get_ingestion_engine
from app.infra_ai.embedding import EmbeddingResponse
from app.ingestion import IngestionContext, IngestionEngine, IngestionResult
from app.ingestion.chunker import FixedSizeChunker
from app.ingestion.nodes import ChunkerNode, IndexerNode, NodeConfig, ParserNode
from app.ingestion.storage import StoredFile
from app.main import create_app
from app.models import User


@pytest.mark.asyncio
async def test_ingestion_engine_parses_chunks_and_indexes_markdown() -> None:
    runtime_dir = create_runtime_dir()
    try:
        source = runtime_dir / "intro.md"
        source.write_text("# Ragent\n支持 pgvector 检索和文档入库。", encoding="utf-8")
        session = AsyncMock()
        embedding_service = AsyncMock()
        embedding_service.embed.return_value = EmbeddingResponse(
            vectors=[[0.1, 0.2], [0.3, 0.4], [0.5, 0.6]],
            model="embed",
        )
        engine = IngestionEngine(
            parser_node=ParserNode(),
            chunker_node=ChunkerNode(FixedSizeChunker(chunk_size=12, overlap=0)),
            indexer_node=IndexerNode(session=session, embedding_service=embedding_service),
        )
        context = IngestionContext(
            kb_id="kb-1",
            doc_id="doc-1",
            file_name="intro.md",
            file_path=source,
            file_type="md",
            user_id="user-1",
        )

        result = await engine.ingest(context)

        assert result == IngestionResult(doc_id="doc-1", chunk_count=3, status="indexed")
        assert context.parsed_document is not None
        assert context.metadata["parser"] == "markdown"
        assert len(context.chunks) == 3
        assert session.execute.await_count == 6
        session.flush.assert_awaited_once()
    finally:
        rmtree(runtime_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_ingestion_engine_executes_configured_pipeline_chain_with_conditions() -> None:
    runtime_dir = create_runtime_dir()
    try:
        source = runtime_dir / "intro.txt"
        source.write_text("Ragent Python 可编排入库流水线", encoding="utf-8")
        session = AsyncMock()
        embedding_service = AsyncMock()
        embedding_service.embed.return_value = EmbeddingResponse(vectors=[[0.1, 0.2]], model="embed")
        engine = IngestionEngine(
            parser_node=ParserNode(),
            chunker_node=ChunkerNode(FixedSizeChunker(chunk_size=999, overlap=0)),
            indexer_node=IndexerNode(session=session, embedding_service=embedding_service),
        )
        context = IngestionContext(
            kb_id="kb-1",
            doc_id="doc-1",
            file_name="intro.txt",
            file_path=source,
            file_type="txt",
            user_id="user-1",
        )

        result = await engine.ingest(
            context,
            pipeline_nodes=[
                NodeConfig(node_id="parser-a", node_type="parser", next_node_id="skip-a"),
                NodeConfig(
                    node_id="skip-a",
                    node_type="chunker",
                    next_node_id="chunker-a",
                    condition={"field": "file_type", "equals": "pdf"},
                ),
                NodeConfig(
                    node_id="chunker-a",
                    node_type="chunker",
                    next_node_id="indexer-a",
                    options={"chunkSize": 999, "overlap": 0},
                ),
                NodeConfig(node_id="indexer-a", node_type="indexer"),
            ],
        )

        assert result.status == "indexed"
        assert context.status == "completed"
        assert [log["nodeId"] for log in context.logs] == ["parser-a", "skip-a", "chunker-a", "indexer-a"]
        assert context.logs[1]["output"] == {"skipped": True}
        assert len(context.chunks) == 1
        session.flush.assert_awaited_once()
    finally:
        rmtree(runtime_dir, ignore_errors=True)


def test_upload_document_api_triggers_ingestion() -> None:
    runtime_dir = create_runtime_dir()
    app = create_app()
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    captured_contexts: list[IngestionContext] = []

    class FakeStorage:
        async def save_upload(self, kb_id: str, upload) -> StoredFile:
            target = runtime_dir / (upload.filename or "upload.txt")
            target.write_bytes(await upload.read())
            return StoredFile(
                file_id="doc-1",
                original_name=upload.filename or "upload.txt",
                file_type="txt",
                file_size=target.stat().st_size,
                path=target,
            )

    class FakeEngine:
        async def ingest(self, context: IngestionContext) -> IngestionResult:
            captured_contexts.append(context)
            return IngestionResult(doc_id=context.doc_id, chunk_count=1, status="indexed")

    async def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_file_storage] = lambda: FakeStorage()
    app.dependency_overrides[get_ingestion_engine] = lambda: FakeEngine()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/ragent/knowledge-base/kb-1/docs/upload",
            files={"file": ("intro.txt", b"hello ragent", "text/plain")},
        )

        assert response.status_code == 200
        assert response.json() == {
            "code": "0",
            "message": "success",
            "data": {
                "id": "doc-1",
                "kbId": "kb-1",
                "docName": "intro.txt",
                "sourceType": "file",
                "sourceLocation": str(runtime_dir / "intro.txt"),
                "scheduleEnabled": None,
                "scheduleCron": None,
                "enabled": True,
                "chunkCount": 1,
                "fileUrl": str(runtime_dir / "intro.txt"),
                "fileType": "txt",
                "fileSize": 12,
                "processMode": "chunk",
                "chunkStrategy": None,
                "chunkConfig": None,
                "pipelineId": None,
                "status": "indexed",
                "createdBy": None,
                "updatedBy": None,
                "createTime": None,
                "updateTime": None,
            },
        }
        assert captured_contexts[0].kb_id == "kb-1"
        assert captured_contexts[0].user_id == "1"
    finally:
        rmtree(runtime_dir, ignore_errors=True)


def create_runtime_dir() -> Path:
    path = Path("test_runtime") / uuid4().hex
    path.mkdir(parents=True, exist_ok=True)
    return path


@pytest.mark.asyncio
async def test_parser_node_parses_docx_document() -> None:
    from docx import Document

    runtime_dir = create_runtime_dir()
    try:
        source = runtime_dir / "intro.docx"
        document = Document()
        document.add_paragraph("Ragent 支持复杂 Word 文档解析")
        document.save(source)
        context = IngestionContext(
            kb_id="kb-1",
            doc_id="doc-1",
            file_name="intro.docx",
            file_path=source,
            file_type="docx",
            user_id="user-1",
        )

        result = await ParserNode().execute(context, NodeConfig(node_id="parser", node_type="parser"))

        assert result.success is True
        assert context.parsed_document is not None
        assert context.metadata["parser"] == "docx"
        assert "复杂 Word 文档解析" in context.parsed_document.text
    finally:
        rmtree(runtime_dir, ignore_errors=True)
