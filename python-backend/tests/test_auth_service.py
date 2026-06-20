import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import RagentException
from app.core.security import decode_access_token, hash_password
from app.models import User
from app.services.auth_service import login


@pytest.mark.asyncio
async def test_login_returns_access_token_for_valid_user() -> None:
    user = User(username="admin", password=hash_password("secret"), status=1)
    user.id = 1
    session = AsyncMock()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)

        token = await login(session, "admin", "secret")

    payload = decode_access_token(token.access_token)

    assert token.token_type == "Bearer"
    assert payload is not None
    assert payload["sub"] == "1"


@pytest.mark.asyncio
async def test_login_rehashes_legacy_sha256_password_after_success() -> None:
    legacy_hash = f"sha256${hashlib.sha256('secret'.encode('utf-8')).hexdigest()}"
    user = User(username="admin", password=legacy_hash, status=1)
    user.id = 1
    session = AsyncMock()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)

        await login(session, "admin", "secret")

    assert user.password.startswith("pbkdf2_sha256$")
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_login_rejects_invalid_password() -> None:
    user = User(username="admin", password=hash_password("secret"), status=1)
    session = AsyncMock()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)

        with pytest.raises(RagentException) as exc_info:
            await login(session, "admin", "wrong")

    assert exc_info.value.code == "40101"


@pytest.mark.asyncio
async def test_login_rejects_disabled_user() -> None:
    user = User(username="admin", password=hash_password("secret"), status=0)
    session = AsyncMock()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)

        with pytest.raises(RagentException) as exc_info:
            await login(session, "admin", "secret")

    assert exc_info.value.code == "40102"
