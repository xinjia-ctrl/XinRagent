import asyncio
import os
import subprocess
import sys
from contextlib import suppress
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
import redis.asyncio as redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config import settings
from app.infra.task_queue import RocketMQTaskQueue, TaskMessage
from app.infra_ai.embedding import EmbeddingRequest, EmbeddingResponse
from app.mcp.client import HttpMCPClient
from app.mcp.core import MCPRequest
from app.mcp.server import create_mcp_app
from app.rag.retrieve import MilvusVectorStoreService, VectorCollectionSpec, VectorIndexChunk

pytestmark = pytest.mark.integration


def _require_real_services_enabled() -> None:
    if os.getenv("REAL_SERVICES_SMOKE_ENABLED", "").lower() not in {"1", "true", "yes"}:
        pytest.skip("设置 REAL_SERVICES_SMOKE_ENABLED=true 后才运行真实服务端到端冒烟测试")


def _backend_dir() -> Path:
    return Path(__file__).resolve().parents[1]


def _require_optional_module(module_name: str, install_hint: str) -> None:
    try:
        __import__(module_name)
    except ImportError as exc:
        pytest.fail(f"真实服务冒烟测试缺少依赖 {module_name}，请先安装 {install_hint}: {exc}")


class FixedEmbeddingService:
    async def embed(self, request: EmbeddingRequest) -> EmbeddingResponse:
        assert request.texts
        return EmbeddingResponse(vectors=[[0.11, 0.22, 0.33]], model=request.model)


@pytest.mark.asyncio
async def test_real_postgres_runs_alembic_and_exposes_required_tables() -> None:
    _require_real_services_enabled()
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=_backend_dir(),
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=120,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout

    engine = create_async_engine(settings.database_url, future=True)
    try:
        async with engine.connect() as connection:
            assert await connection.scalar(text("SELECT 1")) == 1
            expected_tables = {
                "t_user",
                "t_conversation",
                "t_message",
                "t_knowledge_base",
                "t_knowledge_vector",
                "t_ingestion_task",
                "t_task_outbox",
                "t_rag_trace_run",
            }
            existing_tables = {
                table_name
                for table_name in await connection.scalars(
                    text(
                        """
                        SELECT table_name
                        FROM information_schema.tables
                        WHERE table_schema = 'public'
                        """
                    )
                )
            }
            assert expected_tables <= existing_tables
            assert await connection.scalar(text("SELECT to_regclass('public.alembic_version')"))
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_real_redis_roundtrip() -> None:
    _require_real_services_enabled()
    client = redis.from_url(settings.redis_url, decode_responses=True)
    key = f"ragent:smoke:{uuid4().hex}"
    try:
        assert await client.ping() is True
        assert await client.set(key, "ok", ex=60) is True
        assert await client.get(key) == "ok"
    finally:
        await client.delete(key)
        await client.aclose()


@pytest.mark.asyncio
async def test_real_milvus_vector_lifecycle() -> None:
    _require_real_services_enabled()
    _require_optional_module("pymilvus", "python-backend[prod]")
    collection_name = f"smoke_milvus_{uuid4().hex[:12]}"
    service = MilvusVectorStoreService(
        embedding_service=FixedEmbeddingService(),
        collection_name=collection_name,
        dimension=3,
    )

    try:
        await service.rebuild_collection(VectorCollectionSpec(name=collection_name, dimension=3))
        await service.index_chunks(
            collection_name,
            [
                VectorIndexChunk(
                    id="smoke-chunk-1",
                    content="Ragent Python Milvus 真实联调冒烟",
                    vector=[0.11, 0.22, 0.33],
                    metadata={"kbId": "kb-smoke", "docId": "doc-smoke"},
                ),
            ],
        )
        chunks = await service.search(
            "Milvus 真实联调",
            top_k=1,
            kb_id="kb-smoke",
            collection_name=collection_name,
        )
        assert chunks
        assert chunks[0].id == "smoke-chunk-1"
    finally:
        await service.drop_collection(collection_name)


@pytest.mark.asyncio
async def test_real_mcp_json_rpc_lifecycle_and_tool_call() -> None:
    _require_real_services_enabled()
    transport = httpx.ASGITransport(app=create_mcp_app())
    client = HttpMCPClient("http://testserver", transport=transport)

    tools = await client.list_tools()
    response = await client.call_tool(
        MCPRequest(
            tool_id="weather_query",
            arguments={"city": "上海", "queryType": "forecast", "days": 1},
        )
    )

    assert any(tool.tool_id == "weather_query" for tool in tools)
    assert response.success is True
    assert "上海" in (response.content or "")


@pytest.mark.asyncio
async def test_real_rocketmq_produces_and_consumes_task() -> None:
    _require_real_services_enabled()
    queue = RocketMQTaskQueue(
        name_server=settings.rocketmq_name_server,
        producer_group=f"{settings.rocketmq_producer_group}-smoke",
        consumer_group=f"{settings.rocketmq_consumer_group}-smoke-{uuid4().hex[:8]}",
        topic=settings.rocketmq_topic,
        dlq_topic=settings.rocketmq_dlq_topic,
        max_attempts=1,
    )
    task_id = f"smoke-{uuid4().hex}"
    stop_event = asyncio.Event()
    received: list[TaskMessage] = []

    async def handle_smoke_task(task: TaskMessage) -> None:
        if task.task_id != task_id:
            return
        received.append(task)
        stop_event.set()

    worker = asyncio.create_task(
        queue.run_worker(
            {"real.smoke": handle_smoke_task},
            stop_event,
            max_attempts=1,
        )
    )
    try:
        await queue.enqueue(
            "real.smoke",
            {"source": "real-services-smoke"},
            task_id=task_id,
            idempotency_key=task_id,
        )
        timeout_seconds = float(os.getenv("REAL_SERVICES_ROCKETMQ_TIMEOUT_SECONDS", "30"))
        await asyncio.wait_for(stop_event.wait(), timeout=timeout_seconds)
    finally:
        stop_event.set()
        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(worker, timeout=5)

    assert received
    assert received[0].payload["source"] == "real-services-smoke"
