from fastapi.testclient import TestClient

from app.api.deps import get_current_user
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
            "id": 1,
            "username": "admin",
            "nickname": "管理员",
            "avatar": None,
            "email": "admin@example.com",
            "phone": None,
            "role": "admin",
        },
    }
