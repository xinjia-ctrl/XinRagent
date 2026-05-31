from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.api.deps import get_current_user
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
