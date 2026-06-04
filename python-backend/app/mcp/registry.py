from app.mcp.core import MCPTool, MCPToolExecutor
from app.mcp.local_executors import SalesMCPExecutor, TicketMCPExecutor, WeatherMCPExecutor


class MCPToolRegistry:
    def __init__(self, executors: list[MCPToolExecutor] | None = None) -> None:
        default_executors = [WeatherMCPExecutor(), SalesMCPExecutor(), TicketMCPExecutor()]
        self._executors = {executor.tool.tool_id: executor for executor in (executors or default_executors)}

    def get_tool(self, tool_id: str) -> MCPTool | None:
        executor = self._executors.get(tool_id)
        return executor.tool if executor is not None else None

    def get_executor(self, tool_id: str) -> MCPToolExecutor | None:
        return self._executors.get(tool_id)

    def list_tools(self) -> list[MCPTool]:
        return [executor.tool for executor in self._executors.values()]
