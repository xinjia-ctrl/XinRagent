from collections.abc import Callable
from typing import Any
from unittest.mock import AsyncMock

import pytest
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, require_admin_user
from app.api.v1.sample_questions import get_sample_question_service
from app.main import create_app
from app.models import User


ADMIN_PATH_PREFIXES = (
    "/api/ragent/admin/dashboard",
    "/api/ragent/rag/traces",
    "/api/ragent/rag/settings",
    "/api/ragent/ingestion",
    "/api/ragent/intent-tree",
    "/api/ragent/mappings",
    "/api/ragent/sample-questions",
    "/api/ragent/knowledge-base",
    "/api/ragent/users",
)


async def override_non_admin_user() -> User:
    user = User(username="member", password="secret", role="user", status=1)
    user.id = 2
    return user


def create_non_admin_client() -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_non_admin_user
    return TestClient(app)


def dependency_tree_contains(dependant: Dependant, target: Callable[..., Any]) -> bool:
    for dependency in dependant.dependencies:
        if dependency.call is target or dependency_tree_contains(dependency, target):
            return True
    return False


def test_admin_routes_depend_on_admin_guard() -> None:
    app = create_app()
    admin_routes = [
        route
        for route in app.routes
        if isinstance(route, APIRoute) and route.path.startswith(ADMIN_PATH_PREFIXES)
    ]

    assert admin_routes
    for route in admin_routes:
        assert dependency_tree_contains(route.dependant, require_admin_user), route.path


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/ragent/admin/dashboard/overview"),
        ("get", "/api/ragent/rag/traces/runs"),
        ("get", "/api/ragent/rag/settings"),
        ("get", "/api/ragent/ingestion/pipelines"),
        ("delete", "/api/ragent/ingestion/pipelines/pipeline-1"),
        ("get", "/api/ragent/intent-tree/trees"),
        ("delete", "/api/ragent/intent-tree/node-1"),
        ("get", "/api/ragent/mappings"),
        ("delete", "/api/ragent/mappings/map-1"),
        ("get", "/api/ragent/sample-questions"),
        ("delete", "/api/ragent/sample-questions/question-1"),
        ("get", "/api/ragent/knowledge-base"),
        ("delete", "/api/ragent/knowledge-base/kb-1"),
        ("get", "/api/ragent/knowledge-base/kb-1/docs"),
        ("delete", "/api/ragent/knowledge-base/docs/doc-1"),
        ("post", "/api/ragent/knowledge-base/docs/doc-1/chunk"),
        ("post", "/api/ragent/knowledge-base/kb-1/docs/upload"),
        ("get", "/api/ragent/users"),
    ],
)
def test_admin_routes_reject_non_admin_user(method: str, path: str) -> None:
    client = create_non_admin_client()

    response = getattr(client, method)(path)

    assert response.status_code == 403
    assert response.json() == {"code": "40301", "message": "无权访问后台管理", "data": None}


def test_public_sample_questions_allow_non_admin_user() -> None:
    app = create_app()
    service = AsyncMock()
    service.list_public_questions.return_value = []
    app.dependency_overrides[get_current_user] = override_non_admin_user
    app.dependency_overrides[get_sample_question_service] = lambda: service
    client = TestClient(app)

    response = client.get("/api/ragent/rag/sample-questions")

    assert response.status_code == 200
    assert response.json()["data"] == []
    service.list_public_questions.assert_awaited_once()
