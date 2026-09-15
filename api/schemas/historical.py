from pydantic import BaseModel


class HistoricalTotals(BaseModel):
    total_poured: int
    total_packed: int
    total_scrap: int
    yield_pct: float


class TrendPoint(BaseModel):
    date: str
    bottles_filled: int


class OperatorOutput(BaseModel):
    operator: str
    bottles_filled: int


class HistoricalFilters(BaseModel):
    resins: list[str]
    operators: list[str]


class HistoricalOut(BaseModel):
    filters: HistoricalFilters
    totals: HistoricalTotals
    trend: list[TrendPoint]
    by_operator: list[OperatorOutput]
