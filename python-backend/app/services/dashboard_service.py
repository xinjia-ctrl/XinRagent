from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.dashboard import (
    DashboardKpi,
    DashboardOverviewKpis,
    DashboardOverviewResponse,
    DashboardPerformanceResponse,
    DashboardTrendPoint,
    DashboardTrendSeries,
    DashboardTrendsResponse,
)


class DashboardService:
    WINDOW_INTERVALS = {
        "1h": "1 hour",
        "24h": "24 hours",
        "7d": "7 days",
        "30d": "30 days",
    }
    TREND_GRANULARITIES = {"hour": "hour", "day": "day"}

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_overview(self, window: str = "24h") -> DashboardOverviewResponse:
        interval = self._interval(window)
        total_users = await self._count("t_user", "deleted = 0")
        total_sessions = await self._count("t_conversation", "deleted = 0")
        total_messages = await self._count("t_message", "deleted = 0")
        active_users = await self._scalar(
            f"""
            SELECT COUNT(DISTINCT user_id)
            FROM t_message
            WHERE deleted = 0 AND create_time >= CURRENT_TIMESTAMP - INTERVAL '{interval}'
            """,
        )
        sessions_window = await self._count_window("t_conversation", interval)
        messages_window = await self._count_window("t_message", interval)
        sessions_prev = await self._count_previous_window("t_conversation", interval)
        messages_prev = await self._count_previous_window("t_message", interval)

        return DashboardOverviewResponse(
            window=window,
            compareWindow=f"previous-{window}",
            updatedAt=self._now_ms(),
            kpis=DashboardOverviewKpis(
                totalUsers=DashboardKpi(value=total_users),
                activeUsers=DashboardKpi(value=active_users),
                totalSessions=DashboardKpi(value=total_sessions),
                sessions24h=DashboardKpi(
                    value=sessions_window,
                    delta=sessions_window - sessions_prev,
                    deltaPct=self._delta_pct(sessions_window, sessions_prev),
                ),
                totalMessages=DashboardKpi(value=total_messages),
                messages24h=DashboardKpi(
                    value=messages_window,
                    delta=messages_window - messages_prev,
                    deltaPct=self._delta_pct(messages_window, messages_prev),
                ),
            ),
        )

    async def get_performance(self, window: str = "24h") -> DashboardPerformanceResponse:
        interval = self._interval(window)
        result = await self.session.execute(
            text(
                f"""
                SELECT
                    COALESCE(AVG(duration_ms), 0) AS avg_latency,
                    COALESCE(PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY duration_ms), 0) AS p95_latency,
                    COUNT(*) AS total_count,
                    COUNT(*) FILTER (WHERE status = 'SUCCESS') AS success_count,
                    COUNT(*) FILTER (WHERE status <> 'SUCCESS') AS error_count,
                    COUNT(*) FILTER (WHERE duration_ms >= 3000) AS slow_count
                FROM t_rag_trace_run
                WHERE deleted = 0 AND create_time >= CURRENT_TIMESTAMP - INTERVAL '{interval}'
                """,
            ),
        )
        row = result.mappings().first() or {}
        total = int(row.get("total_count") or 0)
        success_count = int(row.get("success_count") or 0)
        error_count = int(row.get("error_count") or 0)
        slow_count = int(row.get("slow_count") or 0)
        return DashboardPerformanceResponse(
            window=window,
            avgLatencyMs=float(row.get("avg_latency") or 0),
            p95LatencyMs=float(row.get("p95_latency") or 0),
            successRate=self._rate(success_count, total),
            errorRate=self._rate(error_count, total),
            noDocRate=0,
            slowRate=self._rate(slow_count, total),
        )

    async def get_trends(
        self,
        metric: str = "messages",
        window: str = "7d",
        granularity: str = "day",
    ) -> DashboardTrendsResponse:
        interval = self._interval(window)
        bucket = self.TREND_GRANULARITIES.get(granularity, "day")
        query = self._trend_query(metric, interval, bucket)
        result = await self.session.execute(text(query))
        return DashboardTrendsResponse(
            metric=metric,
            window=window,
            granularity=granularity,
            series=[
                DashboardTrendSeries(
                    name=metric,
                    data=[
                        DashboardTrendPoint(ts=int(row["ts"] or 0), value=float(row["value"] or 0))
                        for row in result.mappings().all()
                    ],
                ),
            ],
        )

    async def _count(self, table: str, where: str) -> int:
        return await self._scalar(f"SELECT COUNT(*) FROM {table} WHERE {where}")

    async def _count_window(self, table: str, interval: str) -> int:
        return await self._scalar(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE deleted = 0 AND create_time >= CURRENT_TIMESTAMP - INTERVAL '{interval}'
            """,
        )

    async def _count_previous_window(self, table: str, interval: str) -> int:
        return await self._scalar(
            f"""
            SELECT COUNT(*)
            FROM {table}
            WHERE deleted = 0
              AND create_time >= CURRENT_TIMESTAMP - INTERVAL '{interval}' * 2
              AND create_time < CURRENT_TIMESTAMP - INTERVAL '{interval}'
            """,
        )

    async def _scalar(self, query: str) -> int:
        value = await self.session.scalar(text(query))
        return int(value or 0)

    @classmethod
    def _trend_query(cls, metric: str, interval: str, bucket: str) -> str:
        if metric == "sessions":
            return cls._count_trend_query("t_conversation", interval, bucket)
        if metric == "errors":
            return cls._count_trend_query("t_rag_trace_run", interval, bucket, "status <> 'SUCCESS'")
        if metric == "latency":
            return f"""
            SELECT
                EXTRACT(EPOCH FROM DATE_TRUNC('{bucket}', create_time)) * 1000 AS ts,
                COALESCE(AVG(duration_ms), 0) AS value
            FROM t_rag_trace_run
            WHERE deleted = 0 AND create_time >= CURRENT_TIMESTAMP - INTERVAL '{interval}'
            GROUP BY DATE_TRUNC('{bucket}', create_time)
            ORDER BY DATE_TRUNC('{bucket}', create_time)
            """
        return cls._count_trend_query("t_message", interval, bucket)

    @staticmethod
    def _count_trend_query(table: str, interval: str, bucket: str, extra_where: str | None = None) -> str:
        where = f"deleted = 0 AND create_time >= CURRENT_TIMESTAMP - INTERVAL '{interval}'"
        if extra_where:
            where += f" AND {extra_where}"
        return f"""
        SELECT
            EXTRACT(EPOCH FROM DATE_TRUNC('{bucket}', create_time)) * 1000 AS ts,
            COUNT(*) AS value
        FROM {table}
        WHERE {where}
        GROUP BY DATE_TRUNC('{bucket}', create_time)
        ORDER BY DATE_TRUNC('{bucket}', create_time)
        """

    @classmethod
    def _interval(cls, window: str) -> str:
        return cls.WINDOW_INTERVALS.get(window, cls.WINDOW_INTERVALS["24h"])

    @staticmethod
    def _now_ms() -> int:
        return int(datetime.now(UTC).timestamp() * 1000)

    @staticmethod
    def _rate(value: int, total: int) -> float:
        return round(value / total, 4) if total else 0

    @staticmethod
    def _delta_pct(current: int, previous: int) -> float:
        if previous == 0:
            return 1 if current else 0
        return round((current - previous) / previous, 4)
