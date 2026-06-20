import pytest
import httpx
from fastapi.testclient import TestClient

from app.infra_ai.chat import ChatRequest, ChatResponse
from app.mcp.client import HttpMCPClient
from app.mcp.core import MCPParameterDef, MCPRequest, MCPResponse, MCPTool
from app.mcp.local_executors import WeatherMCPExecutor
from app.mcp.parameter_extractor import MCPParameterExtractor
from app.mcp.server import create_mcp_app
from app.mcp.service import MCPService
from app.rag.intent import IntentMatch


@pytest.mark.asyncio
async def test_mcp_service_auto_registers_remote_tools(monkeypatch) -> None:
    class FakeHttpMCPClient:
        def __init__(self, server_url: str) -> None:
            self.server_url = server_url

        async def initialize(self) -> bool:
            return True

        async def list_tools(self) -> list[MCPTool]:
            return [
                MCPTool(
                    tool_id="remote_ticket",
                    description="远程工单查询",
                    parameters={"ticketId": MCPParameterDef("工单号", required=True)},
                    mcp_server_url=self.server_url,
                ),
            ]

        async def call_tool(self, request: MCPRequest) -> MCPResponse:
            return MCPResponse.ok(request.tool_id, f"远程工具已调用：{request.arguments}")

    monkeypatch.setattr("app.mcp.service.HttpMCPClient", FakeHttpMCPClient)
    monkeypatch.setattr("app.mcp.service.settings.rag_mcp_servers", "http://mcp.example")
    service = MCPService()

    responses = await service.execute_for_intents(
        question="查询工单 T123",
        intents=[
            IntentMatch(
                intent_id="intent-1",
                intent_code="ticket.remote",
                name="远程工单",
                confidence=0.9,
                mcp_tool_id="remote_ticket",
            ),
        ],
        user_id="user-1",
    )

    assert responses[0].success is True
    assert "远程工具已调用" in (responses[0].content or "")
    assert service.registry.get_tool("remote_ticket") is not None


@pytest.mark.asyncio
async def test_mcp_parameter_extractor_prefers_llm_arguments() -> None:
    class FakeLLMService:
        async def complete(self, request: ChatRequest) -> ChatResponse:
            assert request.extra_body == {"response_format": {"type": "json_object"}}
            return ChatResponse(
                content='{"arguments":{"city":"上海","queryType":"forecast","days":"2","extra":"drop"}}',
                model=request.model,
            )

    extractor = MCPParameterExtractor(llm_service=FakeLLMService())
    request = await extractor.extract(
        question="帮我查上海未来2天天气",
        tool=WeatherMCPExecutor.tool,
        intent=IntentMatch(
            intent_id="intent-weather",
            intent_code="weather",
            name="天气",
            confidence=0.9,
            mcp_tool_id="weather_query",
        ),
        user_id=None,
    )

    assert request.arguments == {"city": "上海", "queryType": "forecast", "days": 2}


def test_mcp_server_handles_json_rpc_tool_list_and_call() -> None:
    client = TestClient(create_mcp_app())

    initialize_response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
    )
    list_response = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    )
    call_response = client.post(
        "/mcp",
        json={
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "weather_query",
                "arguments": {"city": "上海", "queryType": "forecast", "days": 2},
            },
        },
    )

    assert initialize_response.json()["result"]["serverInfo"]["name"] == "ragent-python-mcp"
    tools = list_response.json()["result"]["tools"]
    assert any(tool["name"] == "weather_query" for tool in tools)
    result = call_response.json()["result"]
    assert result["isError"] is False
    assert "上海" in result["content"][0]["text"]


def test_mcp_server_requires_lifecycle_before_tool_discovery() -> None:
    client = TestClient(create_mcp_app())

    before_initialize = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"},
    )
    batch_response = client.post(
        "/mcp",
        json=[
            {"jsonrpc": "2.0", "id": 2, "method": "initialize", "params": {}},
            {"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}},
        ],
    )
    after_initialize = client.post(
        "/mcp",
        json={"jsonrpc": "2.0", "id": 3, "method": "tools/list"},
    )

    assert before_initialize.json()["error"]["code"] == -32602
    assert batch_response.json()[0]["result"]["capabilities"]["tools"]["listChanged"] is True
    assert len(batch_response.json()) == 1
    assert after_initialize.json()["result"]["nextCursor"] is None
    assert after_initialize.json()["result"]["tools"]


@pytest.mark.asyncio
async def test_http_mcp_client_is_compatible_with_asgi_mcp_server() -> None:
    transport = httpx.ASGITransport(app=create_mcp_app())
    client = HttpMCPClient("http://testserver", transport=transport)

    tools = await client.list_tools()
    response = await client.call_tool(
        MCPRequest(
            tool_id="weather_query",
            arguments={"city": "上海", "queryType": "forecast", "days": 1},
        ),
    )

    assert any(tool.tool_id == "weather_query" for tool in tools)
    assert response.success is True
    assert "上海" in (response.content or "")
