import asyncio

from app.core.config import settings
from app.mcp.client import HttpMCPClient
from app.mcp.core import MCPResponse
from app.mcp.parameter_extractor import MCPParameterExtractor
from app.mcp.registry import MCPToolRegistry
from app.rag.intent import IntentMatch


class MCPService:
    def __init__(
        self,
        registry: MCPToolRegistry | None = None,
        extractor: MCPParameterExtractor | None = None,
    ) -> None:
        self.registry = registry or MCPToolRegistry()
        self.extractor = extractor or MCPParameterExtractor()
        self._remote_registered = False

    async def execute_for_intents(
        self,
        *,
        question: str,
        intents: list[IntentMatch],
        user_id: str | None,
    ) -> list[MCPResponse]:
        tasks = [
            self._execute_single(question=question, intent=intent, user_id=user_id)
            for intent in intents
            if intent.mcp_tool_id
        ]
        if not tasks:
            return []
        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [
            result
            for result in results
            if isinstance(result, MCPResponse)
        ]

    async def ensure_remote_tools_registered(self) -> None:
        if self._remote_registered:
            return
        self._remote_registered = True
        servers = self._parse_servers(settings.rag_mcp_servers)
        for server_url in servers:
            client = HttpMCPClient(server_url)
            try:
                await client.initialize()
                tools = await client.list_tools()
            except Exception:
                continue
            for tool in tools:
                if tool.tool_id:
                    self.registry.register_remote_tool(tool)

    async def _execute_single(self, *, question: str, intent: IntentMatch, user_id: str | None) -> MCPResponse:
        assert intent.mcp_tool_id is not None
        await self.ensure_remote_tools_registered()
        tool = self.registry.get_tool(intent.mcp_tool_id)
        if tool is None:
            return MCPResponse.error(intent.mcp_tool_id, "TOOL_NOT_FOUND", "MCP 工具不存在")

        request = self.extractor.extract(question=question, tool=tool, intent=intent, user_id=user_id)
        if tool.mcp_server_url:
            return await HttpMCPClient(tool.mcp_server_url).call_tool(request)

        executor = self.registry.get_executor(tool.tool_id)
        if executor is None:
            return MCPResponse.error(tool.tool_id, "EXECUTOR_NOT_FOUND", "MCP 工具执行器不存在")
        return await executor.execute(request)

    @staticmethod
    def _parse_servers(value: str) -> list[str]:
        return [item.strip() for item in value.split(",") if item.strip()]
