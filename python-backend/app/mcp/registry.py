from app.mcp.client import HttpMCPClient
from app.mcp.core import MCPRequest, MCPResponse, MCPTool, MCPToolExecutor
from app.mcp.local_executors import SalesMCPExecutor, TicketMCPExecutor, WeatherMCPExecutor


class RemoteMCPToolExecutor:
    def __init__(self, tool: MCPTool) -> None:
        self.tool = tool

    async def execute(self, request: MCPRequest) -> MCPResponse:
        if not self.tool.mcp_server_url:
            return MCPResponse.error(self.tool.tool_id, "MCP_SERVER_MISSING", "MCP Server 地址为空")
        return await HttpMCPClient(self.tool.mcp_server_url).call_tool(request)


class MCPToolRegistry:
    def __init__(self, executors: list[MCPToolExecutor] | None = None) -> None:
        default_executors = [WeatherMCPExecutor(), SalesMCPExecutor(), TicketMCPExecutor()]
        self._executors = {executor.tool.tool_id: executor for executor in (executors or default_executors)}

    def register(self, executor: MCPToolExecutor) -> None:
        self._executors[executor.tool.tool_id] = executor

    def register_remote_tool(self, tool: MCPTool) -> None:
        self.register(RemoteMCPToolExecutor(tool))

    def get_tool(self, tool_id: str) -> MCPTool | None:
        executor = self._executors.get(tool_id)
        return executor.tool if executor is not None else None

    def get_executor(self, tool_id: str) -> MCPToolExecutor | None:
        return self._executors.get(tool_id)

    def list_tools(self) -> list[MCPTool]:
        return [executor.tool for executor in self._executors.values()]
