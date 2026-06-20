from typing import Any

import httpx

from app.mcp.core import MCPParameterDef, MCPRequest, MCPResponse, MCPTool


class HttpMCPClient:
    def __init__(
        self,
        server_url: str,
        timeout: float = 20.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.server_url = server_url.rstrip("/")
        self.timeout = timeout
        self.transport = transport
        self._request_id = 1
        self._is_initialized = False

    async def call_tool(self, request: MCPRequest) -> MCPResponse:
        await self.ensure_initialized()
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": request.tool_id, "arguments": request.arguments},
        }
        async with self._http_client() as client:
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

    async def initialize(self) -> bool:
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ragent-python", "version": "0.1.0"},
            },
        }
        async with self._http_client() as client:
            response = await client.post(self._endpoint(), json=payload)
            response.raise_for_status()
            body = response.json()
        if body.get("error"):
            return False
        await self._send_initialized_notification()
        self._is_initialized = True
        return True

    async def ensure_initialized(self) -> bool:
        if self._is_initialized:
            return True
        return await self.initialize()

    async def list_tools(self) -> list[MCPTool]:
        if not await self.ensure_initialized():
            return []
        payload = {
            "jsonrpc": "2.0",
            "id": self._next_id(),
            "method": "tools/list",
        }
        async with self._http_client() as client:
            response = await client.post(self._endpoint(), json=payload)
            response.raise_for_status()
            body = response.json()
        if body.get("error"):
            return []
        tools = (body.get("result") or {}).get("tools") or []
        return [self._to_tool(tool) for tool in tools if isinstance(tool, dict)]

    def _endpoint(self) -> str:
        return self.server_url if self.server_url.endswith("/mcp") else f"{self.server_url}/mcp"

    def _next_id(self) -> int:
        current = self._request_id
        self._request_id += 1
        return current

    def _http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(timeout=self.timeout, transport=self.transport)

    @staticmethod
    def _extract_text(result: dict[str, Any]) -> str | None:
        content = result.get("content")
        if not isinstance(content, list):
            return None
        segments = [item.get("text") for item in content if isinstance(item, dict) and item.get("text")]
        return "\n".join(segments) if segments else None

    def _to_tool(self, payload: dict[str, Any]) -> MCPTool:
        schema = payload.get("inputSchema") or {}
        properties = schema.get("properties") if isinstance(schema, dict) else {}
        required = set(schema.get("required") or []) if isinstance(schema, dict) else set()
        parameters = {}
        if isinstance(properties, dict):
            for name, definition in properties.items():
                if not isinstance(definition, dict):
                    continue
                parameters[name] = MCPParameterDef(
                    description=definition.get("description", ""),
                    type=definition.get("type", "string"),
                    required=name in required,
                    default=definition.get("default"),
                    enum_values=list(definition.get("enum") or []),
                )
        return MCPTool(
            tool_id=payload.get("name", ""),
            description=payload.get("description", ""),
            parameters=parameters,
            mcp_server_url=self.server_url,
        )

    async def _send_initialized_notification(self) -> None:
        payload = {
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        }
        async with self._http_client() as client:
            response = await client.post(self._endpoint(), json=payload)
            response.raise_for_status()
