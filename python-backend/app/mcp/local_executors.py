from datetime import date, timedelta
import random

from app.mcp.core import MCPParameterDef, MCPRequest, MCPResponse, MCPTool


class WeatherMCPExecutor:
    tool = MCPTool(
        tool_id="weather_query",
        description="查询城市天气信息，支持当前天气和未来天气预报",
        parameters={
            "city": MCPParameterDef("城市名称", required=True),
            "queryType": MCPParameterDef(
                "查询类型",
                default="current",
                enum_values=["current", "forecast"],
            ),
            "days": MCPParameterDef("预报天数", type="integer", default=3),
        },
        require_user_id=False,
    )

    async def execute(self, request: MCPRequest) -> MCPResponse:
        city = request.arguments.get("city")
        if not city:
            return MCPResponse.error(self.tool.tool_id, "INVALID_PARAMS", "请提供城市名称")
        query_type = request.arguments.get("queryType") or "current"
        days = int(request.arguments.get("days") or 3)
        days = min(max(days, 1), 7)

        if query_type == "forecast":
            lines = [f"【{city} 未来{days}天天气预报】"]
            for offset in range(days):
                current = date.today() + timedelta(days=offset)
                weather = self._weather(city, offset)
                lines.append(f"{current:%m-%d}: {weather}，{18 + offset}~{25 + offset}°C")
            return MCPResponse.ok(self.tool.tool_id, "\n".join(lines))

        return MCPResponse.ok(self.tool.tool_id, f"【{city} 今日天气】晴转多云，22~29°C，东南风 2 级。")

    @staticmethod
    def _weather(city: str, offset: int) -> str:
        values = ["晴", "多云", "阴", "小雨", "阵雨"]
        return values[(hash(city) + offset) % len(values)]


class SalesMCPExecutor:
    tool = MCPTool(
        tool_id="sales_query",
        description="查询软件销售数据，支持地区、时间、产品、销售人员等维度",
        parameters={
            "region": MCPParameterDef("地区", enum_values=["华东", "华南", "华北", "西南", "西北"]),
            "period": MCPParameterDef("时间段", default="本月", enum_values=["本月", "上月", "本季度", "上季度", "本年"]),
            "product": MCPParameterDef("产品", enum_values=["企业版", "专业版", "基础版"]),
            "queryType": MCPParameterDef(
                "查询类型",
                default="summary",
                enum_values=["summary", "ranking", "detail", "trend"],
            ),
            "limit": MCPParameterDef("返回数量", type="integer", default=10),
        },
    )

    async def execute(self, request: MCPRequest) -> MCPResponse:
        region = request.arguments.get("region") or "全国"
        period = request.arguments.get("period") or "本月"
        query_type = request.arguments.get("queryType") or "summary"
        seed = hash((region, period, request.user_id)) & 0xFFFF
        random.seed(seed)
        total = random.randint(300, 1200)
        orders = random.randint(20, 90)

        if query_type == "ranking":
            content = f"【{period}{region}销售排名】\n第1名: 张三 - ¥{total * 0.32:.2f} 万\n第2名: 李四 - ¥{total * 0.26:.2f} 万"
        elif query_type == "trend":
            content = f"【{period}{region}销售趋势】销售额 ¥{total:.2f} 万，环比增长 {random.randint(3, 18)}%。"
        else:
            content = f"【{period}{region}销售数据汇总】\n总销售额: ¥{total:.2f} 万\n成交订单: {orders} 笔"
        return MCPResponse.ok(self.tool.tool_id, content)


class TicketMCPExecutor:
    tool = MCPTool(
        tool_id="ticket_query",
        description="查询客户技术支持工单数据，支持按地区、状态、优先级、产品等筛选",
        parameters={
            "region": MCPParameterDef("地区", enum_values=["华东", "华南", "华北", "西南", "西北"]),
            "status": MCPParameterDef("状态", enum_values=["待处理", "处理中", "已解决", "已关闭"]),
            "priority": MCPParameterDef("优先级", enum_values=["紧急", "高", "中", "低"]),
            "queryType": MCPParameterDef("查询类型", default="summary", enum_values=["summary", "list", "stats"]),
            "limit": MCPParameterDef("返回数量", type="integer", default=10),
        },
    )

    async def execute(self, request: MCPRequest) -> MCPResponse:
        region = request.arguments.get("region") or "全国"
        status = request.arguments.get("status") or "全部状态"
        total = 42 + (hash((region, status)) % 30)
        content = f"【客户工单汇总概览】\n筛选: {region} / {status}\n工单总数: {total} 个\n待处理: {total // 4} 个\n处理中: {total // 3} 个"
        return MCPResponse.ok(self.tool.tool_id, content)
