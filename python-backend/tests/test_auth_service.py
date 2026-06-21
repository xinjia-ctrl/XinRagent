import hashlib
from unittest.mock import AsyncMock, patch

import pytest

from app.core.auth_audit import get_auth_audit_store
from app.core.auth_tokens import get_token_revocation_store
from app.core.exceptions import RagentException
from app.core.security import create_access_token, decode_access_token, decode_refresh_token, hash_password
from app.models import User
from app.services.auth_service import login, logout_token, refresh_token


@pytest.mark.asyncio
async def test_login_returns_access_token_for_valid_user() -> None:
    _reset_auth_test_stores()
    user = User(username="admin", password=hash_password("secret"), status=1)
    user.id = 1
    session = AsyncMock()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)

        token = await login(session, "admin", "secret")

    payload = decode_access_token(token.access_token)

    assert token.token_type == "Bearer"
    assert token.refresh_token
    assert payload is not None
    assert payload["sub"] == "1"
    assert decode_refresh_token(token.refresh_token)["type"] == "refresh"
    assert get_auth_audit_store().events[-1].event_type == "login"
    assert get_auth_audit_store().events[-1].success is True


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
    _reset_auth_test_stores()
    user = User(username="admin", password=hash_password("secret"), status=1)
    session = AsyncMock()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)

        with pytest.raises(RagentException) as exc_info:
            await login(session, "admin", "wrong")

    assert exc_info.value.code == "40101"
    assert get_auth_audit_store().events[-1].success is False


@pytest.mark.asyncio
async def test_login_rejects_disabled_user() -> None:
    user = User(username="admin", password=hash_password("secret"), status=0)
    session = AsyncMock()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)

        with pytest.raises(RagentException) as exc_info:
            await login(session, "admin", "secret")

    assert exc_info.value.code == "40102"


@pytest.mark.asyncio
async def test_refresh_token_rotates_and_revokes_old_refresh_token() -> None:
    _reset_auth_test_stores()
    user = User(username="admin", password=hash_password("secret"), status=1)
    user.id = "1"
    session = AsyncMock()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)
        original = await login(session, "admin", "secret")
    original_refresh_payload = decode_refresh_token(original.refresh_token)

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get = AsyncMock(return_value=user)
        refreshed = await refresh_token(session, original.refresh_token)

    assert refreshed.access_token != original.access_token
    assert refreshed.refresh_token != original.refresh_token
    assert await get_token_revocation_store().is_revoked(original_refresh_payload["jti"]) is True


@pytest.mark.asyncio
async def test_logout_revokes_access_token_jti() -> None:
    _reset_auth_test_stores()
    token = create_access_token("1", expires_in=60)
    payload = decode_access_token(token)

    await logout_token(payload)

    assert await get_token_revocation_store().is_revoked(payload["jti"]) is True


def _reset_auth_test_stores() -> None:
    token_store = get_token_revocation_store()
    audit_store = get_auth_audit_store()
    if hasattr(token_store, "clear"):
        token_store.clear()
    if hasattr(audit_store, "clear"):
        audit_store.clear()
