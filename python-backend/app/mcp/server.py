from dataclasses import dataclass
from functools import lru_cache
from typing import Any

from fastapi import APIRouter, Body, Depends, FastAPI, Request
from starlette.responses import Response

from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging
from app.mcp.core import MCPSessionState, MCPParameterDef, MCPRequest, MCPResponse, MCPTool
from app.mcp.registry import MCPToolRegistry

router = APIRouter(tags=["mcp-server"])


@dataclass
class MCPSession:
    state: MCPSessionState = MCPSessionState.NEW
    client_name: str | None = None
    client_version: str | None = None
    protocol_version: str | None = None

    def mark_initialized(self, params: dict[str, Any]) -> None:
        client_info = params.get("clientInfo") if isinstance(params.get("clientInfo"), dict) else {}
        self.client_name = client_info.get("name")
        self.client_version = client_info.get("version")
        self.protocol_version = params.get("protocolVersion")
        self.state = MCPSessionState.INITIALIZED

    def mark_ready(self) -> None:
        self.state = MCPSessionState.READY


@lru_cache
def get_mcp_registry() -> MCPToolRegistry:
    return MCPToolRegistry()


@router.post("/mcp")
async def handle_mcp_json_rpc(
    request: Request,
    payload: dict[str, Any] | list[dict[str, Any]] = Body(...),
    registry: MCPToolRegistry = Depends(get_mcp_registry),
):
    session = getattr(request.app.state, "mcp_session", None)
    if session is None:
        session = MCPSession()
        request.app.state.mcp_session = session
    if isinstance(payload, list):
        responses = [await _handle_single(item, registry, session) for item in payload]
        responses = [response for response in responses if response is not None]
        return responses or Response(status_code=204)
    response = await _handle_single(payload, registry, session)
    return response or Response(status_code=204)


def create_mcp_app(registry: MCPToolRegistry | None = None) -> FastAPI:
    configure_logging()
    app = FastAPI(title="ragent-mcp-server")
    register_exception_handlers(app)
    app.state.mcp_session = MCPSession()
    if registry is not None:
        app.dependency_overrides[get_mcp_registry] = lambda: registry
    app.include_router(router)
    return app


async def _handle_single(
    payload: dict[str, Any],
    registry: MCPToolRegistry,
    session: MCPSession,
) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return _error(None, -32600, "Invalid Request")
    request_id = payload.get("id")
    method = payload.get("method")
    if payload.get("jsonrpc") != "2.0" or not method:
        return _error(request_id, -32600, "Invalid Request")
    if request_id is None:
        try:
            await _dispatch(method, payload.get("params") or {}, registry, session)
        except Exception:
            return None
        return None
    try:
        result = await _dispatch(method, payload.get("params") or {}, registry, session)
    except ValueError as exc:
        return _error(request_id, -32602, str(exc))
    except LookupError as exc:
        return _error(request_id, -32601, str(exc))
    except Exception as exc:
        return _error(request_id, -32000, str(exc))
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


async def _dispatch(
    method: str,
    params: Any,
    registry: MCPToolRegistry,
    session: MCPSession,
) -> dict[str, Any]:
    if method == "initialize":
        if not isinstance(params, dict):
            raise ValueError("initialize params must be object")
        session.mark_initialized(params)
        return {
            "protocolVersion": "2024-11-05",
            "capabilities": {"tools": {"listChanged": True}},
            "serverInfo": {"name": "ragent-python-mcp", "version": "0.1.0"},
        }
    if method == "notifications/initialized":
        session.mark_ready()
        return {}
    if method == "ping":
        return {}
    if method == "tools/list":
        _require_initialized(session)
        return {"tools": [_tool_payload(tool) for tool in registry.list_tools()], "nextCursor": None}
    if method == "tools/call":
        _require_initialized(session)
        if not isinstance(params, dict):
            raise ValueError("tools/call params must be object")
        return await _call_tool(params, registry)
    raise LookupError(f"Method not found: {method}")


async def _call_tool(params: dict[str, Any], registry: MCPToolRegistry) -> dict[str, Any]:
    tool_name = str(params.get("name") or "")
    arguments = params.get("arguments") or {}
    if not tool_name:
        raise ValueError("tools/call params.name is required")
    if not isinstance(arguments, dict):
        raise ValueError("tools/call params.arguments must be object")

    executor = registry.get_executor(tool_name)
    if executor is None:
        raise LookupError(f"Tool not found: {tool_name}")
    response = await executor.execute(
        MCPRequest(tool_id=tool_name, arguments=arguments, user_id=arguments.get("userId")),
    )
    return _tool_result(response)


def _tool_payload(tool: MCPTool) -> dict[str, Any]:
    required = [name for name, parameter in tool.parameters.items() if parameter.required]
    return {
        "name": tool.tool_id,
        "description": tool.description,
        "inputSchema": {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                name: _parameter_payload(parameter)
                for name, parameter in tool.parameters.items()
            },
            "required": required,
        },
    }


def _require_initialized(session: MCPSession) -> None:
    if session.state == MCPSessionState.NEW:
        raise ValueError("MCP session must be initialized first")


def _parameter_payload(parameter: MCPParameterDef) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": parameter.type,
        "description": parameter.description,
    }
    if parameter.enum_values:
        payload["enum"] = parameter.enum_values
    if parameter.default is not None:
        payload["default"] = parameter.default
    return payload


def _tool_result(response: MCPResponse) -> dict[str, Any]:
    content = response.content if response.success else response.error_message or "MCP tool call failed"
    return {
        "content": [{"type": "text", "text": content or ""}],
        "isError": not response.success,
    }


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }
