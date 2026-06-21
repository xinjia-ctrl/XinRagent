from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.auth_audit import record_auth_audit
from app.core.auth_tokens import get_token_revocation_store
from app.core.exceptions import RagentException
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    needs_password_rehash,
    verify_password,
)
from app.models import User
from app.repositories import UserRepository
from app.schemas.auth import TokenResponse


async def authenticate_user(session: AsyncSession, username: str, password: str) -> User:
    repository = UserRepository(session)
    user = await repository.get_by_username(username)
    if user is None or not verify_password(password, user.password):
        raise RagentException(message="用户名或密码错误", code="40101", status_code=401)
    if user.status != 1:
        raise RagentException(message="用户已被禁用", code="40102", status_code=403)
    if needs_password_rehash(user.password):
        user.password = hash_password(password)
        await session.commit()
    return user


async def login(session: AsyncSession, username: str, password: str) -> TokenResponse:
    try:
        user = await authenticate_user(session, username, password)
    except RagentException as exc:
        await record_auth_audit(
            "login",
            success=False,
            username=username,
            reason=exc.code,
        )
        raise
    await record_auth_audit("login", success=True, username=username, user_id=str(user.id))
    return _token_response(user)


async def refresh_token(session: AsyncSession, refresh_token_value: str) -> TokenResponse:
    payload = decode_refresh_token(refresh_token_value)
    if payload is None:
        await record_auth_audit("refresh", success=False, reason="invalid_refresh_token")
        raise RagentException(message="无效或过期的 refresh token", code="40100", status_code=401)

    revocation_store = get_token_revocation_store()
    if await revocation_store.is_revoked(str(payload["jti"])):
        await record_auth_audit(
            "refresh",
            success=False,
            user_id=str(payload.get("sub")),
            token_jti=str(payload["jti"]),
            reason="revoked_refresh_token",
        )
        raise RagentException(message="refresh token 已失效，请重新登录", code="40100", status_code=401)

    repository = UserRepository(session)
    user = await repository.get(str(payload["sub"]))
    if user is None or user.deleted != 0:
        raise RagentException(message="用户不存在", code="40103", status_code=401)
    if user.status != 1:
        raise RagentException(message="用户已被禁用", code="40102", status_code=403)

    await revocation_store.revoke(str(payload["jti"]), int(payload["exp"]))
    await record_auth_audit(
        "refresh",
        success=True,
        user_id=str(user.id),
        username=user.username,
        token_jti=str(payload["jti"]),
    )
    return _token_response(user)


async def logout_token(payload: dict) -> None:
    await get_token_revocation_store().revoke(str(payload["jti"]), int(payload["exp"]))
    await record_auth_audit(
        "logout",
        success=True,
        user_id=str(payload.get("sub")),
        token_jti=str(payload["jti"]),
    )


def _token_response(user: User) -> TokenResponse:
    expires_in = settings.auth_token_expire_seconds
    refresh_expires_in = settings.auth_refresh_token_expire_seconds
    access_token = create_access_token(str(user.id), expires_in=expires_in)
    refresh_token_value = create_refresh_token(str(user.id), expires_in=refresh_expires_in)
    return TokenResponse(
        access_token=access_token,
        token=access_token,
        refresh_token=refresh_token_value,
        refreshToken=refresh_token_value,
        userId=str(user.id),
        username=user.username,
        role=user.role,
        avatar=user.avatar,
        expires_in=expires_in,
        refresh_expires_in=refresh_expires_in,
    )
