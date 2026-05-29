from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.infra_ai.config import default_embedding_targets
from app.infra_ai.embedding import RoutingEmbeddingService
from app.ingestion import IngestionContext, IngestionEngine
from app.ingestion.nodes import ChunkerNode, IndexerNode, ParserNode
from app.ingestion.storage import LocalFileStorage
from app.models import User
from app.schemas.ingestion import UploadedDocumentResponse

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


@router.post("/{kb_id}/docs/upload", response_model=ApiResponse[UploadedDocumentResponse])
async def upload_document_api(
    kb_id: str,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    storage: LocalFileStorage = Depends(get_file_storage),
    ingestion_engine: IngestionEngine = Depends(get_ingestion_engine),
) -> ApiResponse[UploadedDocumentResponse]:
    stored_file = await storage.save_upload(kb_id, file)
    ingestion_result = await ingestion_engine.ingest(
        IngestionContext(
            kb_id=kb_id,
            doc_id=stored_file.file_id,
            file_name=stored_file.original_name,
            file_path=stored_file.path,
            file_type=stored_file.file_type,
            user_id=str(user.id),
        ),
    )
    return success(
        UploadedDocumentResponse(
            kb_id=kb_id,
            doc_id=stored_file.file_id,
            file_name=stored_file.original_name,
            file_type=stored_file.file_type,
            file_size=stored_file.file_size,
            storage_path=str(stored_file.path),
            status=ingestion_result.status,
            chunk_count=ingestion_result.chunk_count,
        ),
    )
