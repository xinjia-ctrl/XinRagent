from typing import Any

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth_tokens import get_token_revocation_store
from app.core.exceptions import RagentException
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models import User
from app.repositories import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    authorization: str | None = Header(default=None, alias="Authorization"),
) -> str:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    if authorization:
        if authorization.lower().startswith("bearer "):
            return authorization[7:].strip()
        return authorization.strip()
    if credentials is not None:
        return credentials.credentials
    else:
        raise RagentException(message="未登录或 token 缺失", code="40100", status_code=401)


async def get_token_payload(token: str = Depends(get_access_token)) -> dict[str, Any]:
    payload = decode_access_token(token)
    if payload is None:
        raise RagentException(message="无效或过期的 token", code="40100", status_code=401)
    if await get_token_revocation_store().is_revoked(str(payload["jti"])):
        raise RagentException(message="token 已失效，请重新登录", code="40100", status_code=401)
    return payload


async def get_current_user(
    payload: dict[str, Any] = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    user_id = payload.get("sub")
    if user_id is None:
        raise RagentException(message="无效或过期的 token", code="40100", status_code=401)

    repository = UserRepository(session)
    user = await repository.get(str(user_id))
    if user is None:
        raise RagentException(message="用户不存在", code="40103", status_code=401)
    if user.status != 1:
        raise RagentException(message="用户已被禁用", code="40102", status_code=403)
    return user


def require_admin_user(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise RagentException(message="无权访问后台管理", code="40301", status_code=403)
    return user
