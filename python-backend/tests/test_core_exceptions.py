from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.core.exceptions import RagentException, register_exception_handlers
from app.core.responses import fail, success


def create_test_app() -> FastAPI:
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/business-error")
    async def business_error() -> None:
        raise RagentException(message="参数错误", code="40001", status_code=400)

    @app.get("/http-error")
    async def http_error() -> None:
        raise HTTPException(status_code=404, detail="资源不存在")

    @app.get("/unexpected-error")
    async def unexpected_error() -> None:
        raise RuntimeError("boom")

    return app


def test_success_response_model() -> None:
    response = success({"id": 1})

    assert response.model_dump() == {"code": "0", "message": "success", "data": {"id": 1}}


def test_fail_response_model() -> None:
    response = fail(code="40001", message="参数错误")

    assert response.model_dump() == {"code": "40001", "message": "参数错误", "data": None}


def test_ragent_exception_returns_unified_response() -> None:
    client = TestClient(create_test_app())

    response = client.get("/business-error")

    assert response.status_code == 400
    assert response.json() == {"code": "40001", "message": "参数错误", "data": None}


def test_http_exception_returns_unified_response() -> None:
    client = TestClient(create_test_app())

    response = client.get("/http-error")

    assert response.status_code == 404
    assert response.json() == {"code": "404", "message": "资源不存在", "data": None}


def test_unhandled_exception_returns_unified_response() -> None:
    client = TestClient(create_test_app(), raise_server_exceptions=False)

    response = client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json() == {"code": "500", "message": "internal server error", "data": None}
