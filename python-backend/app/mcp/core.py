from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class MCPParameterDef:
    description: str
    type: str = "string"
    required: bool = False
    default: Any | None = None
    enum_values: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class MCPTool:
    tool_id: str
    description: str
    parameters: dict[str, MCPParameterDef] = field(default_factory=dict)
    require_user_id: bool = True
    mcp_server_url: str | None = None


@dataclass(frozen=True)
class MCPRequest:
    tool_id: str
    arguments: dict[str, Any] = field(default_factory=dict)
    user_id: str | None = None


@dataclass(frozen=True)
class MCPResponse:
    tool_id: str
    success: bool
    content: str | None = None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def ok(cls, tool_id: str, content: str) -> "MCPResponse":
        return cls(tool_id=tool_id, success=True, content=content)

    @classmethod
    def error(cls, tool_id: str, code: str, message: str) -> "MCPResponse":
        return cls(tool_id=tool_id, success=False, error_code=code, error_message=message)


class MCPToolExecutor(Protocol):
    tool: MCPTool

    async def execute(self, request: MCPRequest) -> MCPResponse:
        ...
