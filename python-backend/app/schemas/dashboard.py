from pydantic import BaseModel


class DashboardKpi(BaseModel):
    value: int | float
    delta: int | float | None = None
    deltaPct: float | None = None


class DashboardOverviewKpis(BaseModel):
    totalUsers: DashboardKpi
    activeUsers: DashboardKpi
    totalSessions: DashboardKpi
    sessions24h: DashboardKpi
    totalMessages: DashboardKpi
    messages24h: DashboardKpi


class DashboardOverviewResponse(BaseModel):
    window: str
    compareWindow: str
    updatedAt: int
    kpis: DashboardOverviewKpis


class DashboardPerformanceResponse(BaseModel):
    window: str
    avgLatencyMs: float
    p95LatencyMs: float
    successRate: float
    errorRate: float
    noDocRate: float
    slowRate: float


class DashboardTrendPoint(BaseModel):
    ts: int
    value: int | float


class DashboardTrendSeries(BaseModel):
    name: str
    data: list[DashboardTrendPoint]


class DashboardTrendsResponse(BaseModel):
    metric: str
    window: str
    granularity: str
    series: list[DashboardTrendSeries]
