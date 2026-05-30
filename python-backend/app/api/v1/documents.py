from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.document import KnowledgeChunkResponse, KnowledgeDocumentResponse
from app.services.document_service import DocumentService

router = APIRouter(prefix="/knowledge-base", tags=["documents"])


def get_document_service(session: AsyncSession = Depends(get_db_session)) -> DocumentService:
    return DocumentService(session)


@router.get("/{kb_id}/docs", response_model=ApiResponse[list[KnowledgeDocumentResponse]])
async def list_documents_api(
    kb_id: str,
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[list[KnowledgeDocumentResponse]]:
    return success(await service.list_documents(kb_id))


@router.get("/docs/{doc_id}", response_model=ApiResponse[KnowledgeDocumentResponse])
async def get_document_api(
    doc_id: str,
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[KnowledgeDocumentResponse]:
    return success(await service.get_document(doc_id))


@router.get("/docs/{doc_id}/chunks", response_model=ApiResponse[list[KnowledgeChunkResponse]])
async def list_chunks_api(
    doc_id: str,
    _: User = Depends(get_current_user),
    service: DocumentService = Depends(get_document_service),
) -> ApiResponse[list[KnowledgeChunkResponse]]:
    return success(await service.list_chunks(doc_id))
