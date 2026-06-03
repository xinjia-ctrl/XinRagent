import re

from fastapi.routing import APIRoute

from app.main import create_app


EXPECTED_FRONTEND_ROUTES = {
    ("POST", "/api/ragent/auth/login"),
    ("POST", "/api/ragent/auth/logout"),
    ("GET", "/api/ragent/user/me"),
    ("PUT", "/api/ragent/user/password"),
    ("GET", "/api/ragent/users"),
    ("POST", "/api/ragent/users"),
    ("PUT", "/api/ragent/users/{}"),
    ("DELETE", "/api/ragent/users/{}"),
    ("GET", "/api/ragent/conversations"),
    ("PUT", "/api/ragent/conversations/{}"),
    ("DELETE", "/api/ragent/conversations/{}"),
    ("GET", "/api/ragent/conversations/{}/messages"),
    ("POST", "/api/ragent/conversations/messages/{}/feedback"),
    ("GET", "/api/ragent/rag/v3/chat"),
    ("POST", "/api/ragent/rag/v3/chat"),
    ("POST", "/api/ragent/rag/v3/stop"),
    ("GET", "/api/ragent/rag/settings"),
    ("GET", "/api/ragent/rag/sample-questions"),
    ("GET", "/api/ragent/rag/traces/runs"),
    ("GET", "/api/ragent/rag/traces/runs/{}"),
    ("GET", "/api/ragent/rag/traces/runs/{}/nodes"),
    ("GET", "/api/ragent/admin/dashboard/overview"),
    ("GET", "/api/ragent/admin/dashboard/performance"),
    ("GET", "/api/ragent/admin/dashboard/trends"),
    ("GET", "/api/ragent/knowledge-base"),
    ("POST", "/api/ragent/knowledge-base"),
    ("GET", "/api/ragent/knowledge-base/chunk-strategies"),
    ("GET", "/api/ragent/knowledge-base/{}"),
    ("PUT", "/api/ragent/knowledge-base/{}"),
    ("DELETE", "/api/ragent/knowledge-base/{}"),
    ("GET", "/api/ragent/knowledge-base/{}/docs"),
    ("POST", "/api/ragent/knowledge-base/{}/docs/upload"),
    ("GET", "/api/ragent/knowledge-base/docs/search"),
    ("GET", "/api/ragent/knowledge-base/docs/{}"),
    ("PUT", "/api/ragent/knowledge-base/docs/{}"),
    ("POST", "/api/ragent/knowledge-base/docs/{}/chunk"),
    ("PATCH", "/api/ragent/knowledge-base/docs/{}/enable"),
    ("DELETE", "/api/ragent/knowledge-base/docs/{}"),
    ("GET", "/api/ragent/knowledge-base/docs/{}/chunks"),
    ("POST", "/api/ragent/knowledge-base/docs/{}/chunks"),
    ("PUT", "/api/ragent/knowledge-base/docs/{}/chunks/{}"),
    ("DELETE", "/api/ragent/knowledge-base/docs/{}/chunks/{}"),
    ("PATCH", "/api/ragent/knowledge-base/docs/{}/chunks/{}/enable"),
    ("PATCH", "/api/ragent/knowledge-base/docs/{}/chunks/batch-enable"),
    ("GET", "/api/ragent/knowledge-base/docs/{}/chunk-logs"),
    ("GET", "/api/ragent/ingestion/pipelines"),
    ("POST", "/api/ragent/ingestion/pipelines"),
    ("GET", "/api/ragent/ingestion/pipelines/{}"),
    ("PUT", "/api/ragent/ingestion/pipelines/{}"),
    ("DELETE", "/api/ragent/ingestion/pipelines/{}"),
    ("GET", "/api/ragent/ingestion/tasks"),
    ("POST", "/api/ragent/ingestion/tasks"),
    ("POST", "/api/ragent/ingestion/tasks/upload"),
    ("GET", "/api/ragent/ingestion/tasks/{}"),
    ("GET", "/api/ragent/ingestion/tasks/{}/nodes"),
    ("GET", "/api/ragent/intent-tree/trees"),
    ("POST", "/api/ragent/intent-tree"),
    ("PUT", "/api/ragent/intent-tree/{}"),
    ("DELETE", "/api/ragent/intent-tree/{}"),
    ("POST", "/api/ragent/intent-tree/batch/enable"),
    ("POST", "/api/ragent/intent-tree/batch/disable"),
    ("POST", "/api/ragent/intent-tree/batch/delete"),
    ("GET", "/api/ragent/mappings"),
    ("POST", "/api/ragent/mappings"),
    ("PUT", "/api/ragent/mappings/{}"),
    ("DELETE", "/api/ragent/mappings/{}"),
    ("GET", "/api/ragent/sample-questions"),
    ("POST", "/api/ragent/sample-questions"),
    ("PUT", "/api/ragent/sample-questions/{}"),
    ("DELETE", "/api/ragent/sample-questions/{}"),
}


def test_frontend_contract_routes_are_registered() -> None:
    app = create_app()
    actual_routes = {
        (method, _normalize_route_path(route.path))
        for route in app.routes
        if isinstance(route, APIRoute)
        for method in route.methods
        if method not in {"HEAD", "OPTIONS"}
    }

    missing = sorted(EXPECTED_FRONTEND_ROUTES - actual_routes)

    assert missing == []


def _normalize_route_path(path: str) -> str:
    return re.sub(r"\{[^}]+}", "{}", path)
