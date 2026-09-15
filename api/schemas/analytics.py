from pydantic import BaseModel


class AnalyticsKpis(BaseModel):
    total_poured_7d: int
    pour_delta_pct: float
    yield_7d: float
    yield_target_pct: float
    total_scrap_7d: int
    downtime_hours_7d: float
    downtime_minutes_7d: int


class LiveTicker(BaseModel):
    expected_now_l: float
    projected_daily_l: float


class TrendPoint(BaseModel):
    date: str
    units: int


class ResinOutput(BaseModel):
    resin: str
    units: int
    color: str


class DowntimeReason(BaseModel):
    reason: str
    minutes: float


class HeatmapCell(BaseModel):
    operator: str
    date: str
    units: int


class WeightReading(BaseModel):
    timestamp: str
    deviation_g: float
    pump_station: str
    resin_type: str | None
    check_weight_g: float | None
    operator_name: str
    status: str | None


class PumpDeviation(BaseModel):
    pump_station: str
    mean_deviation: float
    count: int


class FillWeightOut(BaseModel):
    has_readings: bool
    samples: int
    in_band_pct: str
    mean_deviation: float
    kg_above_target: float
    scatter: list[WeightReading]
    by_pump: list[PumpDeviation]
    worst_pump_note: str | None


class AnalyticsOverviewOut(BaseModel):
    kpis: AnalyticsKpis
    live_ticker: LiveTicker
    velocity_trend: list[TrendPoint]
    formulation_output: list[ResinOutput]
    downtime_pareto: list[DowntimeReason]
    operator_matrix: list[HeatmapCell]
    top_operators: list[str]
    fill_weight: FillWeightOut
