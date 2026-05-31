from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.db.session import get_db_session
from app.main import create_app
from app.models import User


async def override_db_session() -> AsyncIterator[AsyncMock]:
    yield AsyncMock()


def create_authenticated_test_user() -> User:
    user = User(username="admin", password=hash_password("secret"), role="admin", status=1)
    user.id = 1
    return user


def test_login_api_returns_access_token() -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    user = create_authenticated_test_user()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)

        response = client.post(
            "/api/ragent/auth/login",
            json={"username": "admin", "password": "secret"},
        )

    body = response.json()

    assert response.status_code == 200
    assert body["code"] == "0"
    assert body["data"]["token_type"] == "Bearer"
    assert body["data"]["access_token"]


def test_logout_api_requires_authorization() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.post("/api/ragent/auth/logout")

    assert response.status_code == 401
    assert response.json()["code"] == "40100"


def test_logout_api_accepts_valid_token() -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    user = create_authenticated_test_user()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)
        login_response = client.post(
            "/api/ragent/auth/login",
            json={"username": "admin", "password": "secret"},
        )

    token = login_response.json()["data"]["access_token"]
    response = client.post(
        "/api/ragent/auth/logout",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {"code": "0", "message": "success", "data": None}


def test_logout_api_accepts_raw_authorization_token() -> None:
    app = create_app()
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)
    user = create_authenticated_test_user()

    with patch("app.services.auth_service.UserRepository") as repository_class:
        repository_class.return_value.get_by_username = AsyncMock(return_value=user)
        login_response = client.post(
            "/api/ragent/auth/login",
            json={"username": "admin", "password": "secret"},
        )

    token = login_response.json()["data"]["token"]
    response = client.post(
        "/api/ragent/auth/logout",
        headers={"Authorization": token},
    )

    assert response.status_code == 200
    assert response.json() == {"code": "0", "message": "success", "data": None}


def test_protected_user_api_rejects_missing_authorization() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/api/ragent/user/me")

    assert response.status_code == 401
    assert response.json() == {"code": "40100", "message": "未登录或 token 缺失", "data": None}
