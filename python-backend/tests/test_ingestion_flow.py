import json
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
from app.ingestion.nodes import ChunkerNode, FetcherNode, IndexerNode, NodeConfig, ParserNode
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
        assert context.metadata["title"] == "Ragent"
        assert len(context.chunks) == 3
        assert context.chunk_metadata[0]["chunkStrategy"] == "fixed_size"
        assert context.chunk_metadata[0]["chunkSummary"]
        assert session.execute.await_count == 6
        vector_metadata = _vector_metadata_from_session(session)
        assert vector_metadata[0]["title"] == "Ragent"
        assert vector_metadata[0]["chunkIndex"] == 0
        assert vector_metadata[0]["chunkStrategy"] == "fixed_size"
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


@pytest.mark.asyncio
async def test_ingestion_engine_executes_full_configured_etl_pipeline() -> None:
    runtime_dir = create_runtime_dir()
    try:
        source = runtime_dir / "guide.md"
        source.write_text("# 入库指南\nRagent 入库 ETL 支持解析、增强、分块、富化和索引。", encoding="utf-8")
        session = AsyncMock()
        embedding_service = AsyncMock()
        embedding_service.embed.return_value = EmbeddingResponse(vectors=[[0.1, 0.2]], model="embed")
        engine = IngestionEngine(
            parser_node=ParserNode(),
            chunker_node=ChunkerNode(),
            indexer_node=IndexerNode(session=session, embedding_service=embedding_service),
        )
        context = IngestionContext(
            kb_id="kb-1",
            doc_id="doc-1",
            file_name="guide.md",
            file_path=source,
            file_type="md",
            user_id="user-1",
        )

        result = await engine.ingest(
            context,
            pipeline_nodes=[
                NodeConfig(node_id="fetch", node_type="fetcher", next_node_id="parse"),
                NodeConfig(node_id="parse", node_type="parser", next_node_id="enhance"),
                NodeConfig(
                    node_id="enhance",
                    node_type="enhancer",
                    next_node_id="chunk",
                    options={"tasks": [{"type": "metadata"}, {"type": "keywords"}]},
                ),
                NodeConfig(
                    node_id="chunk",
                    node_type="chunker",
                    next_node_id="enrich",
                    options={"strategy": "structure_aware", "targetChars": 500, "maxChars": 800},
                ),
                NodeConfig(
                    node_id="enrich",
                    node_type="enricher",
                    next_node_id="index",
                    options={
                        "attachDocumentMetadata": False,
                        "tasks": [{"type": "metadata"}, {"type": "summary"}],
                    },
                ),
                NodeConfig(
                    node_id="index",
                    node_type="indexer",
                    options={"embeddingModel": "embed-v2", "metadataFields": ["title", "keywords"]},
                ),
            ],
        )

        assert result == IngestionResult(doc_id="doc-1", chunk_count=1, status="indexed")
        assert [log["nodeType"] for log in context.logs] == [
            "fetcher",
            "parser",
            "enhancer",
            "chunker",
            "enricher",
            "indexer",
        ]
        embedding_service.embed.assert_awaited_once()
        assert embedding_service.embed.await_args.args[0].model == "embed-v2"
        vector_metadata = _vector_metadata_from_session(session)
        assert vector_metadata[0]["title"] == "入库指南"
        assert "keywords" in vector_metadata[0]
        assert vector_metadata[0]["chunkSummary"]
        assert vector_metadata[0]["chunkStrategy"] == "structure_aware"
    finally:
        rmtree(runtime_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_fetcher_node_downloads_url_source(monkeypatch: pytest.MonkeyPatch) -> None:
    runtime_dir = create_runtime_dir()

    class FakeResponse:
        headers = {"content-type": "text/markdown"}
        content = b"# Remote\nURL ingestion"

        def raise_for_status(self) -> None:
            return None

    class FakeAsyncClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args) -> None:
            return None

        async def get(self, url: str) -> FakeResponse:
            assert url == "https://example.test/docs/remote.md"
            return FakeResponse()

    monkeypatch.setattr("app.ingestion.nodes.fetcher_node.httpx.AsyncClient", FakeAsyncClient)
    try:
        context = IngestionContext(
            kb_id="kb-1",
            doc_id="doc-1",
            file_name="remote",
            file_path=runtime_dir / "remote",
            file_type="",
            user_id="user-1",
            source_type="url",
            source_location="https://example.test/docs/remote.md",
        )

        result = await FetcherNode().execute(context, NodeConfig(node_id="fetch", node_type="fetcher"))

        assert result.success is True
        assert context.file_path == runtime_dir / "remote.md"
        assert context.file_type == "md"
        assert context.file_path.read_text(encoding="utf-8") == "# Remote\nURL ingestion"
        assert context.metadata["sourceType"] == "url"
        assert context.metadata["fileSize"] == len(FakeResponse.content)
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


def test_upload_document_api_accepts_url_source() -> None:
    runtime_dir = create_runtime_dir()
    app = create_app()
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    captured_contexts: list[IngestionContext] = []

    class FakeStorage:
        def prepare_remote_source(self, kb_id: str, source_location: str, file_name: str | None = None) -> StoredFile:
            return StoredFile(
                file_id="doc-url",
                original_name="intro.md",
                file_type="md",
                file_size=0,
                path=runtime_dir / kb_id / "doc-url.md",
            )

    class FakeEngine:
        async def ingest(self, context: IngestionContext) -> IngestionResult:
            captured_contexts.append(context)
            return IngestionResult(doc_id=context.doc_id, chunk_count=2, status="indexed")

    async def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_file_storage] = lambda: FakeStorage()
    app.dependency_overrides[get_ingestion_engine] = lambda: FakeEngine()
    client = TestClient(app)

    try:
        response = client.post(
            "/api/ragent/knowledge-base/kb-1/docs/upload",
            data={
                "sourceType": "url",
                "sourceLocation": "https://example.test/intro.md",
                "chunkStrategy": "structure_aware",
                "chunkConfig": '{"targetChars": 100, "maxChars": 120}',
            },
        )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["id"] == "doc-url"
        assert payload["sourceType"] == "url"
        assert payload["sourceLocation"] == "https://example.test/intro.md"
        assert payload["chunkCount"] == 2
        assert captured_contexts[0].source_type == "url"
        assert captured_contexts[0].source_location == "https://example.test/intro.md"
        assert captured_contexts[0].metadata["chunkStrategy"] == "structure_aware"
        assert captured_contexts[0].metadata["chunkConfig"] == {"targetChars": 100, "maxChars": 120}
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


def _vector_metadata_from_session(session: AsyncMock) -> list[dict]:
    payloads: list[dict] = []
    for call in session.execute.await_args_list:
        if len(call.args) < 2 or not isinstance(call.args[1], dict):
            continue
        metadata = call.args[1].get("metadata")
        if metadata:
            payloads.append(json.loads(metadata))
    return payloads
