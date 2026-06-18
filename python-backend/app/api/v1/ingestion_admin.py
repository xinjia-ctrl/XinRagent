from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.ingestion.storage import LocalFileStorage
from app.models import User
from app.schemas.ingestion import (
    IngestionPipelinePageResponse,
    IngestionPipelinePayload,
    IngestionPipelineResponse,
    IngestionResultResponse,
    IngestionTaskCreateRequest,
    IngestionTaskNodeResponse,
    IngestionTaskPageResponse,
    IngestionTaskResponse,
)
from app.services.ingestion_service import IngestionService

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def get_ingestion_service(session: AsyncSession = Depends(get_db_session)) -> IngestionService:
    return IngestionService(session)


def get_ingestion_file_storage() -> LocalFileStorage:
    return LocalFileStorage()


@router.get("/pipelines", response_model=ApiResponse[IngestionPipelinePageResponse])
async def list_ingestion_pipelines_api(
    pageNo: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=200),
    keyword: str | None = None,
    _: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionPipelinePageResponse]:
    return success(await service.list_pipelines(page_no=pageNo, page_size=pageSize, keyword=keyword))


@router.get("/pipelines/{pipeline_id}", response_model=ApiResponse[IngestionPipelineResponse])
async def get_ingestion_pipeline_api(
    pipeline_id: str,
    _: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionPipelineResponse]:
    return success(await service.get_pipeline(pipeline_id))


@router.post("/pipelines", response_model=ApiResponse[IngestionPipelineResponse])
async def create_ingestion_pipeline_api(
    request: IngestionPipelinePayload,
    user: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionPipelineResponse]:
    return success(await service.create_pipeline(request, str(user.id)))


@router.put("/pipelines/{pipeline_id}", response_model=ApiResponse[IngestionPipelineResponse])
async def update_ingestion_pipeline_api(
    pipeline_id: str,
    request: IngestionPipelinePayload,
    user: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionPipelineResponse]:
    return success(await service.update_pipeline(pipeline_id, request, str(user.id)))


@router.delete("/pipelines/{pipeline_id}", response_model=ApiResponse[None])
async def delete_ingestion_pipeline_api(
    pipeline_id: str,
    user: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[None]:
    await service.delete_pipeline(pipeline_id, str(user.id))
    return success()


@router.get("/tasks", response_model=ApiResponse[IngestionTaskPageResponse])
async def list_ingestion_tasks_api(
    pageNo: int = Query(default=1, ge=1),
    pageSize: int = Query(default=10, ge=1, le=200),
    status: str | None = None,
    _: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionTaskPageResponse]:
    return success(await service.list_tasks(page_no=pageNo, page_size=pageSize, status=status))


@router.post("/tasks/upload", response_model=ApiResponse[IngestionResultResponse])
async def upload_ingestion_task_api(
    pipelineId: str = Query(...),
    file: UploadFile = File(...),
    user: User = Depends(require_admin_user),
    storage: LocalFileStorage = Depends(get_ingestion_file_storage),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionResultResponse]:
    stored_file = await storage.save_upload(pipelineId, file)
    return success(
        await service.create_upload_task(
            pipeline_id=pipelineId,
            source_location=str(stored_file.path),
            source_file_name=stored_file.original_name,
            user_id=str(user.id),
        ),
    )


@router.get("/tasks/{task_id}", response_model=ApiResponse[IngestionTaskResponse])
async def get_ingestion_task_api(
    task_id: str,
    _: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionTaskResponse]:
    return success(await service.get_task(task_id))


@router.get("/tasks/{task_id}/nodes", response_model=ApiResponse[list[IngestionTaskNodeResponse]])
async def list_ingestion_task_nodes_api(
    task_id: str,
    _: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[list[IngestionTaskNodeResponse]]:
    return success(await service.list_task_nodes(task_id))


@router.post("/tasks", response_model=ApiResponse[IngestionResultResponse])
async def create_ingestion_task_api(
    request: IngestionTaskCreateRequest,
    user: User = Depends(require_admin_user),
    service: IngestionService = Depends(get_ingestion_service),
) -> ApiResponse[IngestionResultResponse]:
    return success(await service.create_task(request, str(user.id)))
