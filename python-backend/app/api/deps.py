from typing import Any

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.exceptions import RagentException
from app.core.security import decode_access_token

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
