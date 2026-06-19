from typing import Any

from app.core.config import settings
from app.infra_ai.chat import ChatMessage, ChatRequest, RoutingLLMService
from app.mcp.core import MCPParameterDef, MCPRequest, MCPTool
from app.rag.llm_json import compact_json, parse_json_object
from app.rag.intent import IntentMatch


class MCPParameterExtractor:
    def __init__(self, llm_service: RoutingLLMService | None = None, model: str | None = None) -> None:
        self.llm_service = llm_service
        self.model = model or settings.ai_chat_default_model

    async def extract(
        self,
        *,
        question: str,
        tool: MCPTool,
        intent: IntentMatch,
        user_id: str | None,
    ) -> MCPRequest:
        arguments = await self._extract_with_llm(question=question, tool=tool, intent=intent)
        if arguments is None:
            arguments = self._extract_with_rules(question=question, tool=tool)
        arguments = self._normalize_arguments(arguments, tool)
        if tool.require_user_id and user_id:
            arguments.setdefault("userId", user_id)

        return MCPRequest(tool_id=intent.mcp_tool_id or tool.tool_id, arguments=arguments, user_id=user_id)

    def _extract_with_rules(self, *, question: str, tool: MCPTool) -> dict[str, Any]:
        arguments: dict[str, Any] = {}
        text = question.strip()

        for name, parameter in tool.parameters.items():
            value = self._extract_value(text, name, parameter.enum_values)
            if value is None:
                value = parameter.default
            if value is not None:
                arguments[name] = value
        return arguments

    async def _extract_with_llm(
        self,
        *,
        question: str,
        tool: MCPTool,
        intent: IntentMatch,
    ) -> dict[str, Any] | None:
        if self.llm_service is None:
            return None
        prompt = {
            "question": question,
            "intent": {"code": intent.intent_code, "name": intent.name},
            "tool": {
                "toolId": tool.tool_id,
                "description": tool.description,
                "parameters": {
                    name: self._parameter_schema(parameter)
                    for name, parameter in tool.parameters.items()
                },
            },
            "outputSchema": {"arguments": "object"},
        }
        try:
            response = await self.llm_service.complete(
                ChatRequest(
                    messages=[
                        ChatMessage(
                            role="system",
                            content=(
                                "你是 MCP 工具参数提取器。请从用户问题中抽取工具参数，"
                                "只返回 JSON 对象，格式为 {\"arguments\": {...}}。"
                            ),
                        ),
                        ChatMessage(role="user", content=compact_json(prompt)),
                    ],
                    model=self.model,
                    temperature=0.0,
                    extra_body={"response_format": {"type": "json_object"}},
                ),
            )
        except Exception:
            return None
        parsed = parse_json_object(response.content)
        if parsed is None:
            return None
        arguments = parsed.get("arguments")
        return arguments if isinstance(arguments, dict) else None

    def _normalize_arguments(self, arguments: dict[str, Any], tool: MCPTool) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for name, parameter in tool.parameters.items():
            value = arguments.get(name)
            if value is None:
                value = parameter.default
            if value is None and parameter.required:
                continue
            if value is not None:
                normalized[name] = self._coerce_value(value, parameter)
        return normalized

    @staticmethod
    def _extract_value(question: str, name: str, enum_values: list[str]) -> Any | None:
        for candidate in enum_values:
            if candidate and candidate in question:
                return candidate

        if name in {"city", "城市"}:
            for city in ["北京", "上海", "广州", "深圳", "杭州", "成都", "武汉", "南京", "西安", "重庆"]:
                if city in question:
                    return city
        if name == "queryType":
            if "排名" in question:
                return "ranking"
            if "明细" in question or "列表" in question:
                return "detail" if "销售" in question else "list"
            if "趋势" in question:
                return "trend"
            if "预报" in question or "未来" in question:
                return "forecast"
            if "统计" in question or "分析" in question:
                return "stats"
        if name == "days":
            for value in range(1, 8):
                if f"{value}天" in question:
                    return value
        if name == "limit":
            for value in range(1, 21):
                if f"{value}条" in question or f"{value}个" in question:
                    return value
        return None

    @staticmethod
    def _parameter_schema(parameter: MCPParameterDef) -> dict[str, Any]:
        return {
            "description": parameter.description,
            "type": parameter.type,
            "required": parameter.required,
            "default": parameter.default,
            "enum": parameter.enum_values,
        }

    @staticmethod
    def _coerce_value(value: Any, parameter: MCPParameterDef) -> Any:
        if parameter.enum_values:
            text = str(value)
            return text if text in parameter.enum_values else value
        if parameter.type in {"integer", "int"}:
            try:
                return int(value)
            except (TypeError, ValueError):
                return value
        if parameter.type in {"number", "float"}:
            try:
                return float(value)
            except (TypeError, ValueError):
                return value
        if parameter.type == "boolean":
            if isinstance(value, bool):
                return value
            return str(value).lower() in {"true", "1", "yes", "是"}
        return value
