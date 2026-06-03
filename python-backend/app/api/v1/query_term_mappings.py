from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.query_term_mapping import (
    QueryTermMappingPageResponse,
    QueryTermMappingPayload,
)
from app.services.query_term_mapping_service import QueryTermMappingService

router = APIRouter(prefix="/mappings", tags=["query-term-mappings"])


def get_query_term_mapping_service(session: AsyncSession = Depends(get_db_session)) -> QueryTermMappingService:
    return QueryTermMappingService(session)


@router.get("", response_model=ApiResponse[QueryTermMappingPageResponse])
async def list_query_term_mappings_api(
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=200),
    keyword: str | None = None,
    _: User = Depends(get_current_user),
    service: QueryTermMappingService = Depends(get_query_term_mapping_service),
) -> ApiResponse[QueryTermMappingPageResponse]:
    return success(await service.list_mappings(current=current, size=size, keyword=keyword))


@router.post("", response_model=ApiResponse[str])
async def create_query_term_mapping_api(
    request: QueryTermMappingPayload,
    user: User = Depends(get_current_user),
    service: QueryTermMappingService = Depends(get_query_term_mapping_service),
) -> ApiResponse[str]:
    return success(await service.create_mapping(request, str(user.id)))


@router.put("/{mapping_id}", response_model=ApiResponse[None])
async def update_query_term_mapping_api(
    mapping_id: str,
    request: QueryTermMappingPayload,
    user: User = Depends(get_current_user),
    service: QueryTermMappingService = Depends(get_query_term_mapping_service),
) -> ApiResponse[None]:
    await service.update_mapping(mapping_id, request, str(user.id))
    return success()


@router.delete("/{mapping_id}", response_model=ApiResponse[None])
async def delete_query_term_mapping_api(
    mapping_id: str,
    user: User = Depends(get_current_user),
    service: QueryTermMappingService = Depends(get_query_term_mapping_service),
) -> ApiResponse[None]:
    await service.delete_mapping(mapping_id, str(user.id))
    return success()
