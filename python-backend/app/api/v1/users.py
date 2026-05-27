from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.models import User
from app.schemas.user import CurrentUserResponse

router = APIRouter(prefix="/user", tags=["user"])


@router.get("/me", response_model=ApiResponse[CurrentUserResponse])
async def current_user_api(user: User = Depends(get_current_user)) -> ApiResponse[CurrentUserResponse]:
    return success(CurrentUserResponse.model_validate(user))
