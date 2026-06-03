from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.core.responses import ApiResponse, success
from app.models import User
from app.schemas.settings import SystemSettingsResponse
from app.services.settings_service import SettingsService

router = APIRouter(prefix="/rag/settings", tags=["settings"])


def get_settings_service() -> SettingsService:
    return SettingsService()


@router.get("", response_model=ApiResponse[SystemSettingsResponse])
async def get_system_settings_api(
    _: User = Depends(get_current_user),
    service: SettingsService = Depends(get_settings_service),
) -> ApiResponse[SystemSettingsResponse]:
    return success(await service.get_settings())
