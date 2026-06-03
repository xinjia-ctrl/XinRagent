from unittest.mock import AsyncMock

from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1.dashboard import get_dashboard_service
from app.api.v1.settings import get_settings_service
from app.api.v1.traces import get_trace_service
from app.main import create_app
from app.models import User
from app.schemas.dashboard import (
    DashboardKpi,
    DashboardOverviewKpis,
    DashboardOverviewResponse,
    DashboardPerformanceResponse,
    DashboardTrendPoint,
    DashboardTrendSeries,
    DashboardTrendsResponse,
)
from app.schemas.settings import (
    AiProviderSettings,
    AiSelectionSettings,
    AiSettings,
    AiStreamSettings,
    ModelCandidate,
    ModelGroup,
    RagDefaultSettings,
    RagMemorySettings,
    RagQueryRewriteSettings,
    RagRateLimitGlobalSettings,
    RagRateLimitSettings,
    RagSettings,
    SystemSettingsResponse,
    UploadSettings,
)
from app.schemas.trace import TraceDetailResponse, TraceNodeResponse, TraceRunPageResponse, TraceRunResponse


async def override_current_user() -> User:
    user = User(username="admin", password="secret", role="admin", status=1)
    user.id = 1
    return user


def create_admin_client(
    trace_service: object | None = None,
    dashboard_service: object | None = None,
    settings_service: object | None = None,
) -> TestClient:
    app = create_app()
    app.dependency_overrides[get_current_user] = override_current_user
    if trace_service is not None:
        app.dependency_overrides[get_trace_service] = lambda: trace_service
    if dashboard_service is not None:
        app.dependency_overrides[get_dashboard_service] = lambda: dashboard_service
    if settings_service is not None:
        app.dependency_overrides[get_settings_service] = lambda: settings_service
    return TestClient(app)


def test_trace_page_detail_and_nodes_match_frontend_contract() -> None:
    service = AsyncMock()
    service.list_runs.return_value = TraceRunPageResponse(
        records=[
            TraceRunResponse(
                traceId="trace-1",
                traceName="rag_chat",
                conversationId="conv-1",
                taskId="task-1",
                userName="admin",
                userId="1",
                status="SUCCESS",
                durationMs=12,
            ),
        ],
        total=1,
        size=5,
        current=2,
        pages=1,
    )
    service.get_run_detail.return_value = TraceDetailResponse(
        run=TraceRunResponse(traceId="trace-1", status="SUCCESS"),
        nodes=[TraceNodeResponse(traceId="trace-1", nodeId="node-1", nodeName="pipeline", status="SUCCESS")],
    )
    service.list_nodes.return_value = [
        TraceNodeResponse(
            traceId="trace-1",
            nodeId="node-1",
            parentNodeId=None,
            depth=0,
            nodeType="PIPELINE",
            nodeName="pipeline",
            className="StreamChatPipeline",
            methodName="execute",
            status="SUCCESS",
            durationMs=12,
        ),
    ]
    client = create_admin_client(trace_service=service)

    page_response = client.get(
        "/api/ragent/rag/traces/runs?current=2&size=5&traceId=trace-1&conversationId=conv-1&taskId=task-1&status=SUCCESS",
    )
    detail_response = client.get("/api/ragent/rag/traces/runs/trace-1")
    nodes_response = client.get("/api/ragent/rag/traces/runs/trace-1/nodes")

    assert page_response.json()["data"]["records"][0]["traceId"] == "trace-1"
    assert detail_response.json()["data"]["nodes"][0]["nodeName"] == "pipeline"
    assert nodes_response.json()["data"][0]["className"] == "StreamChatPipeline"
    service.list_runs.assert_awaited_once_with(
        current=2,
        size=5,
        trace_id="trace-1",
        conversation_id="conv-1",
        task_id="task-1",
        status="SUCCESS",
    )
    service.list_nodes.assert_awaited_once_with("trace-1")


def test_dashboard_apis_match_frontend_contract() -> None:
    service = AsyncMock()
    service.get_overview.return_value = DashboardOverviewResponse(
        window="24h",
        compareWindow="previous-24h",
        updatedAt=1710000000000,
        kpis=DashboardOverviewKpis(
            totalUsers=DashboardKpi(value=10),
            activeUsers=DashboardKpi(value=3),
            totalSessions=DashboardKpi(value=8),
            sessions24h=DashboardKpi(value=2, delta=1, deltaPct=1),
            totalMessages=DashboardKpi(value=20),
            messages24h=DashboardKpi(value=6, delta=2, deltaPct=0.5),
        ),
    )
    service.get_performance.return_value = DashboardPerformanceResponse(
        window="24h",
        avgLatencyMs=120,
        p95LatencyMs=300,
        successRate=0.9,
        errorRate=0.1,
        noDocRate=0,
        slowRate=0.05,
    )
    service.get_trends.return_value = DashboardTrendsResponse(
        metric="messages",
        window="7d",
        granularity="day",
        series=[DashboardTrendSeries(name="messages", data=[DashboardTrendPoint(ts=1710000000000, value=5)])],
    )
    client = create_admin_client(dashboard_service=service)

    overview_response = client.get("/api/ragent/admin/dashboard/overview?window=24h")
    performance_response = client.get("/api/ragent/admin/dashboard/performance?window=24h")
    trends_response = client.get("/api/ragent/admin/dashboard/trends?metric=messages&window=7d&granularity=day")

    assert overview_response.json()["data"]["kpis"]["messages24h"]["value"] == 6
    assert performance_response.json()["data"]["successRate"] == 0.9
    assert trends_response.json()["data"]["series"][0]["data"][0]["value"] == 5
    service.get_overview.assert_awaited_once_with(window="24h")
    service.get_performance.assert_awaited_once_with(window="24h")
    service.get_trends.assert_awaited_once_with(metric="messages", window="7d", granularity="day")


def test_system_settings_api_matches_frontend_contract() -> None:
    service = AsyncMock()
    service.get_settings.return_value = SystemSettingsResponse(
        upload=UploadSettings(maxFileSize=1024, maxRequestSize=2048),
        rag=RagSettings(
            default=RagDefaultSettings(collectionName="rag_default_store", dimension=1536, metricType="cosine"),
            queryRewrite=RagQueryRewriteSettings(enabled=True, maxHistoryMessages=6, maxHistoryChars=4000),
            rateLimit=RagRateLimitSettings(
                global_=RagRateLimitGlobalSettings(
                    enabled=False,
                    maxConcurrent=100,
                    maxWaitSeconds=30,
                    leaseSeconds=120,
                    pollIntervalMs=250,
                ),
            ),
            memory=RagMemorySettings(
                historyKeepTurns=10,
                summaryStartTurns=12,
                summaryEnabled=False,
                ttlMinutes=1440,
                summaryMaxChars=1200,
                titleMaxLength=30,
            ),
        ),
        ai=AiSettings(
            providers={
                "bailian": AiProviderSettings(url="https://dashscope.aliyuncs.com", apiKey=None, endpoints={}),
            },
            selection=AiSelectionSettings(failureThreshold=3, openDurationMs=60000),
            stream=AiStreamSettings(messageChunkSize=1),
            chat=ModelGroup(
                defaultModel="qwen3-max",
                candidates=[
                    ModelCandidate(
                        id="bailian-chat",
                        provider="bailian",
                        model="qwen3-max",
                        enabled=True,
                        supportsThinking=True,
                    ),
                ],
            ),
            embedding=ModelGroup(defaultModel="qwen-emb-8b", candidates=[]),
            rerank=ModelGroup(defaultModel="qwen3-rerank", candidates=[]),
        ),
    )
    client = create_admin_client(settings_service=service)

    response = client.get("/api/ragent/rag/settings")

    assert response.status_code == 200
    assert response.json()["data"]["rag"]["rateLimit"]["global"]["maxConcurrent"] == 100
    assert response.json()["data"]["ai"]["chat"]["candidates"][0]["supportsThinking"] is True
