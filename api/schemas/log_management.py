from pydantic import BaseModel


class ProductionLogRow(BaseModel):
    id: int
    timestamp: str
    log_type: str
    pump_station: str
    resin_type: str | None
    resin_color: str | None
    operator_name: str
    bottles_filled: int


class ProductionLogFilters(BaseModel):
    log_types: list[str]
    pumps: list[str]
    operators: list[str]
    min_date: str | None
    max_date: str | None


class ProductionLogsOut(BaseModel):
    filters: ProductionLogFilters
    total_matches: int
    rows: list[ProductionLogRow]


class DowntimeLogRow(BaseModel):
    id: int
    timestamp: str
    pump_station: str
    reason: str
    duration_min: int
    operator_name: str


class DowntimeLogFilters(BaseModel):
    pumps: list[str]
    reasons: list[str]
    min_date: str | None
    max_date: str | None


class DowntimeLogsOut(BaseModel):
    filters: DowntimeLogFilters
    total_matches: int
    rows: list[DowntimeLogRow]


class BulkDeleteResult(BaseModel):
    deleted: int
