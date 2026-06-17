import pytest

from app.mcp.core import MCPParameterDef, MCPRequest, MCPResponse, MCPTool
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
