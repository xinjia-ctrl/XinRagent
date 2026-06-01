from math import ceil

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.common.ids import generate_id
from app.core.exceptions import RagentException
from app.core.responses import ApiResponse, success
from app.core.security import hash_password, verify_password
from app.db.session import get_db_session
from app.models import User
from app.repositories import UserRepository
from app.schemas.user import (
    ChangePasswordRequest,
    CurrentUserResponse,
    UserCreateRequest,
    UserItem,
    UserPageResponse,
    UserUpdateRequest,
)

router = APIRouter(tags=["user"])


def require_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise RagentException(message="无权访问用户管理", code="40301", status_code=403)
    return user


@router.get("/user/me", response_model=ApiResponse[CurrentUserResponse])
async def current_user_api(user: User = Depends(get_current_user)) -> ApiResponse[CurrentUserResponse]:
    return success(_to_current_user_response(user))


@router.put("/user/password", response_model=ApiResponse[None])
async def change_password_api(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[None]:
    if not verify_password(request.currentPassword, user.password):
        raise RagentException(message="当前密码错误", code="40001", status_code=400)
    user.password = hash_password(request.newPassword)
    await session.commit()
    return success()


@router.get("/users", response_model=ApiResponse[UserPageResponse])
async def list_users_api(
    current: int = Query(default=1, ge=1),
    size: int = Query(default=10, ge=1, le=100),
    keyword: str | None = None,
    _: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[UserPageResponse]:
    repository = UserRepository(session)
    users, total = await repository.list_page(current=current, size=size, keyword=keyword)
    records = [_to_user_item(user) for user in users]
    return success(
        UserPageResponse(
            records=records,
            total=total,
            size=size,
            current=current,
            pages=ceil(total / size) if total else 0,
        )
    )


@router.post("/users", response_model=ApiResponse[str])
async def create_user_api(
    request: UserCreateRequest,
    _: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[str]:
    repository = UserRepository(session)
    username = request.username.strip()
    if not username:
        raise RagentException(message="用户名不能为空", code="40001", status_code=400)
    if await repository.username_exists(username):
        raise RagentException(message="用户名已存在", code="40002", status_code=400)

    user = User(
        id=generate_id(),
        username=username,
        password=hash_password(request.password),
        role=request.role or "user",
        avatar=request.avatar,
    )
    await repository.add(user)
    await session.commit()
    return success(str(user.id))


@router.put("/users/{user_id}", response_model=ApiResponse[None])
async def update_user_api(
    user_id: str,
    request: UserUpdateRequest,
    _: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[None]:
    repository = UserRepository(session)
    user = await repository.get(user_id)
    if user is None or user.deleted != 0:
        raise RagentException(message="用户不存在", code="40401", status_code=404)

    if request.username is not None:
        username = request.username.strip()
        if not username:
            raise RagentException(message="用户名不能为空", code="40001", status_code=400)
        if await repository.username_exists(username, exclude_id=user_id):
            raise RagentException(message="用户名已存在", code="40002", status_code=400)
        user.username = username
    if request.password:
        user.password = hash_password(request.password)
    if request.role is not None:
        user.role = request.role
    if request.avatar is not None:
        user.avatar = request.avatar

    await session.commit()
    return success()


@router.delete("/users/{user_id}", response_model=ApiResponse[None])
async def delete_user_api(
    user_id: str,
    _: User = Depends(require_admin_user),
    session: AsyncSession = Depends(get_db_session),
) -> ApiResponse[None]:
    repository = UserRepository(session)
    user = await repository.get(user_id)
    if user is None or user.deleted != 0:
        raise RagentException(message="用户不存在", code="40401", status_code=404)
    user.deleted = 1
    await session.commit()
    return success()


def _to_current_user_response(user: User) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=str(user.id),
        userId=str(user.id),
        username=user.username,
        nickname=user.nickname,
        avatar=user.avatar,
        email=user.email,
        phone=user.phone,
        role=user.role,
    )


def _to_user_item(user: User) -> UserItem:
    return UserItem(
        id=str(user.id),
        username=user.username,
        role=user.role,
        avatar=user.avatar,
        createTime=user.create_time,
        updateTime=user.update_time,
    )
