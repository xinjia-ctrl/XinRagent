from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_token_payload
from app.core.responses import ApiResponse, success
from app.db.session import get_db_session
from app.schemas.auth import LoginRequest, TokenResponse
from app.services.auth_service import login

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login_api(
    request: LoginRequest,
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[TokenResponse]:
    token = await login(session, request.username, request.password)
    return success(token)


@router.post("/logout", response_model=ApiResponse[None])
async def logout_api(_: dict = Depends(get_token_payload)) -> ApiResponse[None]:
    return success()
