import json
from json import JSONDecodeError
from functools import lru_cache

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_user
from app.core.config import settings
from app.core.exceptions import RagentException
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.infra import InMemoryUploadRateLimiter, RedisUploadRateLimiter, UploadRateLimiter
from app.infra_ai.config import default_embedding_targets
from app.infra_ai.embedding import RoutingEmbeddingService
from app.ingestion import IngestionContext, IngestionEngine
from app.ingestion.nodes import ChunkerNode, IndexerNode, ParserNode
from app.ingestion.storage import LocalFileStorage
from app.models import User
from app.schemas.document import KnowledgeDocumentResponse
from app.services.document_service import DocumentService
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/knowledge-base", tags=["ingestion"])


def get_file_storage() -> LocalFileStorage:
    return LocalFileStorage()


def get_embedding_service() -> RoutingEmbeddingService:
    return RoutingEmbeddingService(default_embedding_targets())


@lru_cache
def get_upload_rate_limiter() -> UploadRateLimiter:
    if not settings.upload_rate_limit_enabled:
        return InMemoryUploadRateLimiter(settings.upload_rate_limit_per_minute, enabled=False)
    return RedisUploadRateLimiter(
        redis_url=settings.redis_url,
        key_prefix=settings.upload_rate_limit_key_prefix,
        limit_per_minute=settings.upload_rate_limit_per_minute,
        enabled=True,
    )


def get_ingestion_engine(
    session: AsyncSession = Depends(get_db_session),
    embedding_service: RoutingEmbeddingService = Depends(get_embedding_service),
) -> IngestionEngine:
    return IngestionEngine(
        parser_node=ParserNode(),
        chunker_node=ChunkerNode(),
        indexer_node=IndexerNode(session=session, embedding_service=embedding_service),
    )


@router.post("/{kb_id}/docs/upload", response_model=ApiResponse[KnowledgeDocumentResponse])
async def upload_document_api(
    kb_id: str,
    sourceType: str = Form(default="file"),
    file: UploadFile | None = File(default=None),
    sourceLocation: str | None = Form(default=None),
    scheduleEnabled: bool | None = Form(default=None),
    scheduleCron: str | None = Form(default=None),
    processMode: str | None = Form(default="chunk"),
    chunkStrategy: str | None = Form(default=None),
    chunkConfig: str | None = Form(default=None),
    pipelineId: str | None = Form(default=None),
    user: User = Depends(require_admin_user),
    storage: LocalFileStorage = Depends(get_file_storage),
    ingestion_engine: IngestionEngine = Depends(get_ingestion_engine),
    upload_limiter: UploadRateLimiter = Depends(get_upload_rate_limiter),
) -> ApiResponse[KnowledgeDocumentResponse]:
    await upload_limiter.check(str(user.id))
    source_type = _normalize_source_type(sourceType)
    chunk_options = _parse_chunk_config(chunkConfig)

    if source_type == "file":
        if file is None:
            raise RagentException(message="上传文件不能为空", code="DOCUMENT_FILE_REQUIRED", status_code=400)
        stored_file = await storage.save_upload(kb_id, file)
    elif source_type == "url":
        if not sourceLocation:
            raise RagentException(message="URL 数据源不能为空", code="DOCUMENT_SOURCE_URL_REQUIRED", status_code=400)
        stored_file = storage.prepare_remote_source(kb_id, sourceLocation)
    else:
        raise RagentException(message=f"不支持的数据源类型: {source_type}", code="DOCUMENT_SOURCE_UNSUPPORTED")

    resolved_source_location = sourceLocation if source_type == "url" else str(stored_file.path)
    document_service = _get_document_service_from_engine(ingestion_engine)
    if document_service is not None:
        await document_service.create_uploaded_document(
            kb_id=kb_id,
            doc_id=stored_file.file_id,
            doc_name=stored_file.original_name,
            file_url=str(stored_file.path),
            file_type=stored_file.file_type,
            file_size=stored_file.file_size,
            user_id=str(user.id),
            source_type=source_type,
            source_location=resolved_source_location,
            schedule_enabled=scheduleEnabled,
            schedule_cron=scheduleCron,
            process_mode=processMode,
            chunk_strategy=chunkStrategy,
            chunk_config=chunkConfig,
            pipeline_id=pipelineId,
        )
    pipeline_nodes = None
    session = _get_session_from_engine(ingestion_engine)
    if pipelineId and session is not None:
        pipeline_nodes = (await IngestionService(session).get_pipeline(pipelineId)).nodes

    metadata = {
        "sourceType": source_type,
        "sourceLocation": resolved_source_location,
        "processMode": processMode or "chunk",
        "chunkStrategy": chunkStrategy,
        "chunkConfig": chunk_options,
    }
    if pipelineId:
        metadata["pipelineId"] = pipelineId

    context = IngestionContext(
        kb_id=kb_id,
        doc_id=stored_file.file_id,
        file_name=stored_file.original_name,
        file_path=stored_file.path,
        file_type=stored_file.file_type,
        user_id=str(user.id),
        source_type=source_type,
        source_location=resolved_source_location,
        metadata=metadata,
    )
    ingestion_result = (
        await ingestion_engine.ingest(context, pipeline_nodes=pipeline_nodes)
        if pipeline_nodes is not None
        else await ingestion_engine.ingest(context)
    )
    if document_service is not None:
        return success(
            await document_service.complete_document_ingestion(
                stored_file.file_id,
                status=ingestion_result.status,
                chunk_count=ingestion_result.chunk_count,
                user_id=str(user.id),
                file_url=str(context.file_path),
                file_type=context.file_type,
                file_size=_file_size(context.file_path, stored_file.file_size),
            ),
        )

    return success(
        KnowledgeDocumentResponse(
            id=stored_file.file_id,
            kbId=kb_id,
            docName=stored_file.original_name,
            sourceType=source_type,
            sourceLocation=resolved_source_location,
            scheduleEnabled=1 if scheduleEnabled else 0 if scheduleEnabled is not None else None,
            scheduleCron=scheduleCron,
            enabled=True,
            fileUrl=str(context.file_path),
            fileType=context.file_type,
            fileSize=_file_size(context.file_path, stored_file.file_size),
            processMode=processMode,
            chunkStrategy=chunkStrategy,
            chunkConfig=chunkConfig,
            pipelineId=pipelineId,
            status=ingestion_result.status,
            chunkCount=ingestion_result.chunk_count,
        ),
    )


def _get_document_service_from_engine(ingestion_engine: IngestionEngine) -> DocumentService | None:
    session = _get_session_from_engine(ingestion_engine)
    return DocumentService(session) if session is not None else None


def _get_session_from_engine(ingestion_engine: IngestionEngine):
    indexer_node = getattr(ingestion_engine, "indexer_node", None)
    return getattr(indexer_node, "session", None)


def _normalize_source_type(source_type: str | None) -> str:
    normalized = (source_type or "file").lower().strip()
    if normalized in {"http", "https"}:
        return "url"
    return normalized


def _parse_chunk_config(chunk_config: str | None) -> dict:
    if not chunk_config:
        return {}
    try:
        parsed = json.loads(chunk_config)
    except JSONDecodeError as exc:
        raise RagentException(message="chunkConfig 必须是合法 JSON 对象", code="DOCUMENT_CHUNK_CONFIG_INVALID") from exc
    if not isinstance(parsed, dict):
        raise RagentException(message="chunkConfig 必须是 JSON 对象", code="DOCUMENT_CHUNK_CONFIG_INVALID")
    return parsed


def _file_size(path, fallback: int) -> int:
    return path.stat().st_size if path.exists() else fallback
