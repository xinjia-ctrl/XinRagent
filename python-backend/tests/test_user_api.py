from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.api.deps import get_current_user
from app.core.security import hash_password, verify_password
from app.db.session import get_db_session
from app.main import create_app
from app.models import User


def test_current_user_api_returns_authenticated_user() -> None:
    app = create_app()
    user = User(
        username="admin",
        password="secret",
        nickname="管理员",
        email="admin@example.com",
        role="admin",
        status=1,
    )
    user.id = 1

    async def override_current_user() -> User:
        return user

    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)

    response = client.get("/api/ragent/user/me")

    assert response.status_code == 200
    assert response.json() == {
        "code": "0",
        "message": "success",
        "data": {
            "id": "1",
            "userId": "1",
            "username": "admin",
            "nickname": "管理员",
            "avatar": None,
            "email": "admin@example.com",
            "phone": None,
            "role": "admin",
        },
    }


async def override_db_session() -> AsyncMock:
    return AsyncMock()


def test_users_page_api_returns_frontend_page_shape() -> None:
    app = create_app()
    current_user = User(id="1", username="admin", password="secret", role="admin", status=1)
    listed_user = User(id="2", username="member", password="secret", role="user", avatar=None, status=1)

    async def override_current_user() -> User:
        return current_user

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_db_session
    client = TestClient(app)

    with patch("app.api.v1.users.UserRepository") as repository_class:
        repository_class.return_value.list_page = AsyncMock(return_value=([listed_user], 1))

        response = client.get("/api/ragent/users?current=1&size=10")

    assert response.status_code == 200
    assert response.json()["data"] == {
        "records": [
            {
                "id": "2",
                "username": "member",
                "role": "user",
                "avatar": None,
                "createTime": None,
                "updateTime": None,
            }
        ],
        "total": 1,
        "size": 10,
        "current": 1,
        "pages": 1,
    }


def test_users_page_api_rejects_non_admin_user() -> None:
    app = create_app()
    current_user = User(id="1", username="member", password="secret", role="user", status=1)

    async def override_current_user() -> User:
        return current_user

    app.dependency_overrides[get_current_user] = override_current_user
    client = TestClient(app)

    response = client.get("/api/ragent/users")

    assert response.status_code == 403
    assert response.json() == {"code": "40301", "message": "无权访问用户管理", "data": None}


def test_create_user_api_returns_created_user_id() -> None:
    app = create_app()
    current_user = User(id="1", username="admin", password="secret", role="admin", status=1)
    session = AsyncMock()

    async def override_current_user() -> User:
        return current_user

    async def override_session() -> AsyncMock:
        return session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_session
    client = TestClient(app)

    with patch("app.api.v1.users.UserRepository") as repository_class:
        repository = repository_class.return_value
        repository.username_exists = AsyncMock(return_value=False)
        repository.add = AsyncMock()

        response = client.post(
            "/api/ragent/users",
            json={"username": "member", "password": "secret", "role": "user", "avatar": None},
        )

    assert response.status_code == 200
    assert response.json()["data"]
    repository.add.assert_awaited_once()
    session.commit.assert_awaited_once()


def test_update_user_api_updates_existing_user() -> None:
    app = create_app()
    current_user = User(id="1", username="admin", password="secret", role="admin", status=1)
    target_user = User(id="2", username="member", password="secret", role="user", status=1)
    session = AsyncMock()

    async def override_current_user() -> User:
        return current_user

    async def override_session() -> AsyncMock:
        return session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_session
    client = TestClient(app)

    with patch("app.api.v1.users.UserRepository") as repository_class:
        repository = repository_class.return_value
        repository.get = AsyncMock(return_value=target_user)
        repository.username_exists = AsyncMock(return_value=False)

        response = client.put(
            "/api/ragent/users/2",
            json={"username": "operator", "password": "new-secret", "role": "admin"},
        )

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert target_user.username == "operator"
    assert target_user.role == "admin"
    assert verify_password("new-secret", target_user.password)
    session.commit.assert_awaited_once()


def test_delete_user_api_marks_user_deleted() -> None:
    app = create_app()
    current_user = User(id="1", username="admin", password="secret", role="admin", status=1)
    target_user = User(id="2", username="member", password="secret", role="user", status=1)
    session = AsyncMock()

    async def override_current_user() -> User:
        return current_user

    async def override_session() -> AsyncMock:
        return session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_session
    client = TestClient(app)

    with patch("app.api.v1.users.UserRepository") as repository_class:
        repository_class.return_value.get = AsyncMock(return_value=target_user)

        response = client.delete("/api/ragent/users/2")

    assert response.status_code == 200
    assert response.json()["data"] is None
    assert target_user.deleted == 1
    session.commit.assert_awaited_once()


def test_change_password_api_updates_current_user_password() -> None:
    app = create_app()
    current_user = User(
        id="1",
        username="admin",
        password=hash_password("old-secret"),
        role="admin",
        status=1,
    )
    session = AsyncMock()

    async def override_current_user() -> User:
        return current_user

    async def override_session() -> AsyncMock:
        return session

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_db_session] = override_session
    client = TestClient(app)

    response = client.put(
        "/api/ragent/user/password",
        json={"currentPassword": "old-secret", "newPassword": "new-secret"},
    )

    assert response.status_code == 200
    assert verify_password("new-secret", current_user.password)
    session.commit.assert_awaited_once()
