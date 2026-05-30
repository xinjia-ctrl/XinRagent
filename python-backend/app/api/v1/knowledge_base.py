from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.knowledge import (
    DeleteResponse,
    KnowledgeBaseCreateRequest,
    KnowledgeBaseResponse,
    KnowledgeBaseUpdateRequest,
)
from app.services.knowledge_service import KnowledgeService

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


def get_knowledge_service(session: AsyncSession = Depends(get_db_session)) -> KnowledgeService:
    return KnowledgeService(session)


@router.get("", response_model=ApiResponse[list[KnowledgeBaseResponse]])
async def list_knowledge_bases_api(
    _: User = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[list[KnowledgeBaseResponse]]:
    return success(await service.list_knowledge_bases())


@router.post("", response_model=ApiResponse[KnowledgeBaseResponse])
async def create_knowledge_base_api(
    request: KnowledgeBaseCreateRequest,
    user: User = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[KnowledgeBaseResponse]:
    return success(await service.create_knowledge_base(request, str(user.id)))


@router.put("/{kb_id}", response_model=ApiResponse[KnowledgeBaseResponse])
async def update_knowledge_base_api(
    kb_id: str,
    request: KnowledgeBaseUpdateRequest,
    user: User = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[KnowledgeBaseResponse]:
    return success(await service.update_knowledge_base(kb_id, request, str(user.id)))


@router.delete("/{kb_id}", response_model=ApiResponse[DeleteResponse])
async def delete_knowledge_base_api(
    kb_id: str,
    user: User = Depends(get_current_user),
    service: KnowledgeService = Depends(get_knowledge_service),
) -> ApiResponse[DeleteResponse]:
    return success(await service.delete_knowledge_base(kb_id, str(user.id)))
