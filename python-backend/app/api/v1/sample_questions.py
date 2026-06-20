from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_admin_user
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.models import User
from app.schemas.sample_question import (
    SampleQuestionPageResponse,
    SampleQuestionPayload,
    SampleQuestionResponse,
)
from app.services.sample_question_service import SampleQuestionService

router = APIRouter(tags=["sample-questions"])


def get_sample_question_service(session: AsyncSession = Depends(get_db_session)) -> SampleQuestionService:
    return SampleQuestionService(session)


@router.get("/rag/sample-questions", response_model=ApiResponse[list[SampleQuestionResponse]])
async def list_public_sample_questions_api(
    _: User = Depends(get_current_user),
    service: SampleQuestionService = Depends(get_sample_question_service),
) -> ApiResponse[list[SampleQuestionResponse]]:
    return success(await service.list_public_questions())


@router.get("/sample-questions", response_model=ApiResponse[SampleQuestionPageResponse])
async def list_sample_questions_api(
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=200),
    keyword: str | None = None,
    _: User = Depends(require_admin_user),
    service: SampleQuestionService = Depends(get_sample_question_service),
) -> ApiResponse[SampleQuestionPageResponse]:
    return success(await service.list_questions(current=current, size=size, keyword=keyword))


@router.get("/sample-questions/{question_id}", response_model=ApiResponse[SampleQuestionResponse])
async def get_sample_question_api(
    question_id: str,
    _: User = Depends(require_admin_user),
    service: SampleQuestionService = Depends(get_sample_question_service),
) -> ApiResponse[SampleQuestionResponse]:
    return success(await service.get_question(question_id))


@router.post("/sample-questions", response_model=ApiResponse[str])
async def create_sample_question_api(
    request: SampleQuestionPayload,
    _: User = Depends(require_admin_user),
    service: SampleQuestionService = Depends(get_sample_question_service),
) -> ApiResponse[str]:
    return success(await service.create_question(request))


@router.put("/sample-questions/{question_id}", response_model=ApiResponse[None])
async def update_sample_question_api(
    question_id: str,
    request: SampleQuestionPayload,
    _: User = Depends(require_admin_user),
    service: SampleQuestionService = Depends(get_sample_question_service),
) -> ApiResponse[None]:
    await service.update_question(question_id, request)
    return success()


@router.delete("/sample-questions/{question_id}", response_model=ApiResponse[None])
async def delete_sample_question_api(
    question_id: str,
    _: User = Depends(require_admin_user),
    service: SampleQuestionService = Depends(get_sample_question_service),
) -> ApiResponse[None]:
    await service.delete_question(question_id)
    return success()
