from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RagentException
from app.core.security import decode_access_token
from app.db.session import get_db_session
from app.models import User
from app.repositories import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)


def get_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise RagentException(message="未登录或 token 缺失", code="40100", status_code=401)
    return credentials.credentials


def get_token_payload(token: str = Depends(get_access_token)) -> dict[str, Any]:
    payload = decode_access_token(token)
    if payload is None:
        raise RagentException(message="无效或过期的 token", code="40100", status_code=401)
    return payload


async def get_current_user(
    payload: dict[str, Any] = Depends(get_token_payload),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    user_id = payload.get("sub")
    if user_id is None:
        raise RagentException(message="无效或过期的 token", code="40100", status_code=401)

    repository = UserRepository(session)
    user = await repository.get(int(user_id))
    if user is None:
        raise RagentException(message="用户不存在", code="40103", status_code=401)
    if user.status != 1:
        raise RagentException(message="用户已被禁用", code="40102", status_code=403)
    return user
