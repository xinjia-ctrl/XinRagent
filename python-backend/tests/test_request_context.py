from fastapi.testclient import TestClient

from app.core.context import REQUEST_ID_HEADER, get_request_id
from app.main import create_app


def test_request_context_uses_incoming_request_id() -> None:
    app = create_app()

    @app.get("/context-id")
    async def context_id() -> dict[str, str]:
        return {"request_id": get_request_id()}

    client = TestClient(app)

    response = client.get("/context-id", headers={REQUEST_ID_HEADER: "test-request-id"})

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER] == "test-request-id"
    assert response.json() == {"request_id": "test-request-id"}


def test_request_context_generates_request_id() -> None:
    app = create_app()
    client = TestClient(app)

    response = client.get("/health")

    assert response.status_code == 200
    assert response.headers[REQUEST_ID_HEADER]
