from typing import Any

import httpx

from app.mcp.core import MCPRequest, MCPResponse


class HttpMCPClient:
    def __init__(self, server_url: str, timeout: float = 20.0) -> None:
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self._request_id = 1

    async def call_tool(self, request: MCPRequest) -> MCPResponse:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": request.tool_id, "arguments": request.arguments},
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(self._endpoint(), json=payload)
            response.raise_for_status()
            body = response.json()

        if body.get("error"):
            error = body["error"]
            return MCPResponse.error(request.tool_id, str(error.get("code")), error.get("message", "MCP 调用失败"))
        result = body.get("result") or {}
        if result.get("isError"):
            return MCPResponse.error(request.tool_id, "MCP_ERROR", self._extract_text(result) or "MCP 工具返回错误")
        return MCPResponse.ok(request.tool_id, self._extract_text(result) or str(result))

    def _endpoint(self) -> str:
        return self.server_url if self.server_url.endswith("/mcp") else f"{self.server_url}/mcp"

    def _next_id(self) -> int:
        current = self._request_id
        self._request_id += 1
        return current

    @staticmethod
    def _extract_text(result: dict[str, Any]) -> str | None:
        content = result.get("content")
        if not isinstance(content, list):
            return None
        segments = [item.get("text") for item in content if isinstance(item, dict) and item.get("text")]
        return "\n".join(segments) if segments else None
