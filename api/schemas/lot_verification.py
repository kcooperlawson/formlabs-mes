from pydantic import BaseModel


class LotVerificationTotals(BaseModel):
    checks_logged: int
    full_checks: int
    pct_full: float
    flagged: int
    cartridges_pulled: int
    flag_rate: float


class LotCheckOut(BaseModel):
    id: int
    timestamp: str
    operator_name: str
    pump_station: str
    cartridge_type: str
    resin_type: str | None
    resin_color: str | None
    expected_lot: str | None
    entered_lot: str | None
    result: str
    check_level: str
    reason: str | None
    production_log_id: int | None
    photo_filename: str | None


class OperatorCoverage(BaseModel):
    operator_name: str
    checks: int
    full: int
    fast: int
    flags: int
    pct_full: float


class StationCoverage(BaseModel):
    pump_station: str
    checks: int
    flags: int


class LotVerificationOut(BaseModel):
    totals: LotVerificationTotals
    checks: list[LotCheckOut]
    by_operator: list[OperatorCoverage]
    by_station: list[StationCoverage]
