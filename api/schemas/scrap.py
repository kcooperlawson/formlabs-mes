from pydantic import BaseModel


class ScrapTotals(BaseModel):
    empty_scrap: int
    filled_scrap: int
    total_scrap: int


class ResinOutput(BaseModel):
    resin_type: str
    bottles_filled: int
    color: str


class DowntimeReason(BaseModel):
    reason: str
    duration_min: float


class ScrapIntelOut(BaseModel):
    totals: ScrapTotals
    by_resin: list[ResinOutput]
    downtime_by_reason: list[DowntimeReason]
