from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.ingestion import (
    IngestionPipelinePageResponse,
    IngestionPipelinePayload,
    IngestionPipelineResponse,
)
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_ingestion_service(session: AsyncSession = Depends(get_db_session)) -> IngestionService:
    return IngestionService(session)


@router.get("/pipelines", response_model=ApiResponse[IngestionPipelinePageResponse])
async def list_ingestion_pipelines_api(
    pageNo: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=200),
    keyword: str | None = None,
    _: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionPipelinePageResponse]:
    return success(await service.list_pipelines(page_no=pageNo, page_size=pageSize, keyword=keyword))


@router.get("/pipelines/{pipeline_id}", response_model=ApiResponse[IngestionPipelineResponse])
async def get_ingestion_pipeline_api(
    pipeline_id: str,
    _: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionPipelineResponse]:
    return success(await service.get_pipeline(pipeline_id))


@router.post("/pipelines", response_model=ApiResponse[IngestionPipelineResponse])
async def create_ingestion_pipeline_api(
    request: IngestionPipelinePayload,
    user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionPipelineResponse]:
    return success(await service.create_pipeline(request, str(user.id)))


@router.put("/pipelines/{pipeline_id}", response_model=ApiResponse[IngestionPipelineResponse])
async def update_ingestion_pipeline_api(
    pipeline_id: str,
    request: IngestionPipelinePayload,
    user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionPipelineResponse]:
    return success(await service.update_pipeline(pipeline_id, request, str(user.id)))


@router.delete("/pipelines/{pipeline_id}", response_model=ApiResponse[None])
async def delete_ingestion_pipeline_api(
    pipeline_id: str,
    user: User = Depends(get_current_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[None]:
    await service.delete_pipeline(pipeline_id, str(user.id))
    return success()
