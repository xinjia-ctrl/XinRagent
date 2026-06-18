from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_user
from app.core.exceptions import RagentException
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
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
) -> ApiResponse[KnowledgeDocumentResponse]:
    if file is None:
        raise RagentException(message="上传文件不能为空", code="DOCUMENT_FILE_REQUIRED", status_code=400)

    stored_file = await storage.save_upload(kb_id, file)
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
            source_type=sourceType,
            source_location=sourceLocation,
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

    context = IngestionContext(
        kb_id=kb_id,
        doc_id=stored_file.file_id,
        file_name=stored_file.original_name,
        file_path=stored_file.path,
        file_type=stored_file.file_type,
        user_id=str(user.id),
        metadata={"pipelineId": pipelineId} if pipelineId else {},
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
            ),
        )

    return success(
        KnowledgeDocumentResponse(
            id=stored_file.file_id,
            kbId=kb_id,
            docName=stored_file.original_name,
            sourceType=sourceType,
            sourceLocation=sourceLocation or str(stored_file.path),
            scheduleEnabled=1 if scheduleEnabled else 0 if scheduleEnabled is not None else None,
            scheduleCron=scheduleCron,
            enabled=True,
            fileUrl=str(stored_file.path),
            fileType=stored_file.file_type,
            fileSize=stored_file.file_size,
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
