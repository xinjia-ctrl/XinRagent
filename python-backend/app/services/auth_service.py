from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import RagentException
from app.core.security import create_access_token, verify_password
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
    return user


async def login(session: AsyncSession, username: str, password: str) -> TokenResponse:
    user = await authenticate_user(session, username, password)
    expires_in = settings.auth_token_expire_seconds
    access_token = create_access_token(str(user.id), expires_in=expires_in)
    return TokenResponse(access_token=access_token, expires_in=expires_in)
