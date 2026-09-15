from pydantic import BaseModel


class HourlyPoint(BaseModel):
    hour: str  # ISO 8601, floored to the hour
    units: int


class ResinPoint(BaseModel):
    resin: str
    units: int


class ShiftSummaryOut(BaseModel):
    has_logs_today: bool
    units: int
    scrap: int
    yield_pct: float
    logs_submitted: int
    has_output_logs: bool  # False when today's only logs are e.g. downtime/audit
    hourly_timeline: list[HourlyPoint] = []
    by_resin: list[ResinPoint] = []
