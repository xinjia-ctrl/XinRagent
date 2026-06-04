from typing import Any

from app.mcp.core import MCPRequest, MCPTool
from app.rag.intent import IntentMatch


class MCPParameterExtractor:
    def extract(
        self,
        *,
        question: str,
        tool: MCPTool,
        intent: IntentMatch,
        user_id: str | None,
    ) -> MCPRequest:
        arguments: dict[str, Any] = {}
        text = question.strip()

        for name, parameter in tool.parameters.items():
            value = self._extract_value(text, name, parameter.enum_values)
            if value is None:
                value = parameter.default
            if value is not None:
                arguments[name] = value

        if tool.require_user_id and user_id:
            arguments.setdefault("userId", user_id)

        return MCPRequest(tool_id=intent.mcp_tool_id or tool.tool_id, arguments=arguments, user_id=user_id)

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
