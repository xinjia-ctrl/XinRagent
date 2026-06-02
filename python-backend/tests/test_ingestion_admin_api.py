from pathlib import Path
from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.ingestion_admin import get_ingestion_file_storage, get_ingestion_service
from app.ingestion.storage import StoredFile
from app.main import create_app
from app.models import User
from app.schemas.ingestion import (
    IngestionPipelineNodeResponse,
    IngestionPipelinePageResponse,
    IngestionPipelineResponse,
    IngestionResultResponse,
    IngestionTaskNodeResponse,
    IngestionTaskPageResponse,
    IngestionTaskResponse,
)


async def override_current_user() -> User:
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    return user


def create_ingestion_client(service: object, storage: object | None = None) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_ingestion_service] = lambda: service
    if storage is not None:
        app.dependency_overrides[get_ingestion_file_storage] = lambda: storage
    return TestClient(app)


def pipeline_response(pipeline_id: str = "pipe-1") -> IngestionPipelineResponse:
    return IngestionPipelineResponse(
        id=pipeline_id,
        name="默认流水线",
        description="Markdown 入库",
        createdBy="1",
        nodes=[
            IngestionPipelineNodeResponse(
                id="node-row-1",
                nodeId="parser",
                nodeType="parser",
                settings={"parser": "markdown"},
                nextNodeId="chunker",
            ),
        ],
    )


def test_ingestion_pipeline_apis_match_frontend_contract() -> None:
    service = AsyncMock()
    service.list_pipelines.return_value = IngestionPipelinePageResponse(
        records=[pipeline_response()],
        total=1,
        size=5,
        current=2,
        pages=1,
    )
    service.get_pipeline.return_value = pipeline_response()
    service.create_pipeline.return_value = pipeline_response("pipe-new")
    service.update_pipeline.return_value = pipeline_response("pipe-1")
    client = create_ingestion_client(service)

    page_response = client.get("/api/ragent/ingestion/pipelines?pageNo=2&pageSize=5&keyword=默认")
    detail_response = client.get("/api/ragent/ingestion/pipelines/pipe-1")
    create_response = client.post(
        "/api/ragent/ingestion/pipelines",
        json={
            "name": "默认流水线",
            "description": "Markdown 入库",
            "nodes": [
                {
                    "nodeId": "parser",
                    "nodeType": "parser",
                    "settings": {"parser": "markdown"},
                    "nextNodeId": "chunker",
                },
            ],
        },
    )
    update_response = client.put(
        "/api/ragent/ingestion/pipelines/pipe-1",
        json={"name": "默认流水线", "nodes": []},
    )
    delete_response = client.delete("/api/ragent/ingestion/pipelines/pipe-1")

    assert page_response.status_code == 200
    assert page_response.json()["data"]["records"][0]["nodes"][0]["nodeType"] == "parser"
    assert detail_response.json()["data"]["nodes"][0]["nodeId"] == "parser"
    assert create_response.json()["data"]["id"] == "pipe-new"
    assert update_response.json()["data"]["id"] == "pipe-1"
    assert delete_response.json()["data"] is None
    service.list_pipelines.assert_awaited_once_with(page_no=2, page_size=5, keyword="默认")
    service.get_pipeline.assert_awaited_once_with("pipe-1")
    create_request = service.create_pipeline.await_args.args[0]
    update_request = service.update_pipeline.await_args.args[1]
    assert create_request.nodes[0].node_id == "parser"
    assert update_request.nodes == []
    service.delete_pipeline.assert_awaited_once_with("pipe-1", "1")


def test_ingestion_task_apis_match_frontend_contract() -> None:
    service = AsyncMock()
    service.list_tasks.return_value = IngestionTaskPageResponse(
        records=[
            IngestionTaskResponse(
                id="task-1",
                pipelineId="pipe-1",
                sourceType="url",
                sourceLocation="https://example.test/doc",
                status="pending",
                chunkCount=0,
                logs=[],
                metadata={"source": "manual"},
            ),
        ],
        total=1,
        size=10,
        current=1,
        pages=1,
    )
    service.get_task.return_value = IngestionTaskResponse(
        id="task-1",
        pipelineId="pipe-1",
        sourceType="url",
        status="pending",
        chunkCount=0,
    )
    service.list_task_nodes.return_value = [
        IngestionTaskNodeResponse(
            id="task-node-1",
            taskId="task-1",
            pipelineId="pipe-1",
            nodeId="parser",
            nodeType="parser",
            nodeOrder=0,
            status="pending",
        ),
    ]
    service.create_task.return_value = IngestionResultResponse(
        taskId="task-new",
        pipelineId="pipe-1",
        status="pending",
        chunkCount=0,
        message="任务已创建",
    )
    client = create_ingestion_client(service)

    page_response = client.get("/api/ragent/ingestion/tasks?pageNo=1&pageSize=10&status=pending")
    detail_response = client.get("/api/ragent/ingestion/tasks/task-1")
    nodes_response = client.get("/api/ragent/ingestion/tasks/task-1/nodes")
    create_response = client.post(
        "/api/ragent/ingestion/tasks",
        json={
            "pipelineId": "pipe-1",
            "source": {"type": "url", "location": "https://example.test/doc", "fileName": "doc.md"},
            "metadata": {"source": "manual"},
            "vectorSpaceId": {"kbId": "kb-1"},
        },
    )

    assert page_response.json()["data"]["records"][0]["metadata"] == {"source": "manual"}
    assert detail_response.json()["data"]["id"] == "task-1"
    assert nodes_response.json()["data"][0]["nodeId"] == "parser"
    assert create_response.json()["data"]["taskId"] == "task-new"
    service.list_tasks.assert_awaited_once_with(page_no=1, page_size=10, status="pending")
    create_request = service.create_task.await_args.args[0]
    assert create_request.pipeline_id == "pipe-1"
    assert create_request.source.fileName == "doc.md"


def test_ingestion_upload_task_api_saves_file_then_creates_task() -> None:
    service = AsyncMock()
    service.create_upload_task.return_value = IngestionResultResponse(
        taskId="task-upload",
        pipelineId="pipe-1",
        status="pending",
        chunkCount=0,
        message="文件任务已创建",
    )

    class FakeStorage:
        async def save_upload(self, pipeline_id: str, upload) -> StoredFile:
            return StoredFile(
                file_id="file-1",
                original_name=upload.filename or "upload.txt",
                file_type="txt",
                file_size=12,
                path=Path("test_runtime") / pipeline_id / "intro.txt",
            )

    client = create_ingestion_client(service, FakeStorage())

    response = client.post(
        "/api/ragent/ingestion/tasks/upload?pipelineId=pipe-1",
        files={"file": ("intro.txt", b"hello ragent", "text/plain")},
    )

    assert response.status_code == 200
    assert response.json()["data"]["taskId"] == "task-upload"
    service.create_upload_task.assert_awaited_once_with(
        pipeline_id="pipe-1",
        source_location=str(Path("test_runtime") / "pipe-1" / "intro.txt"),
        source_file_name="intro.txt",
        user_id="1",
    )
