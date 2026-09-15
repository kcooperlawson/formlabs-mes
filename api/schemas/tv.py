from pydantic import BaseModel


class TvHealth(BaseModel):
    state: str
    is_alarm: bool
    is_warning: bool
    message: str


class TopPourer(BaseModel):
    operator: str
    rate_lph: float


class PackingBreakdownRow(BaseModel):
    resin: str
    lot_number: str
    units: int
    color: str
    skids: float


class WorkOrderRow(BaseModel):
    resin_type: str
    color: str
    pump_station: str
    current_units: int
    target_units: int
    progress_pct: float


class TvOverviewOut(BaseModel):
    active_shift: str
    health: TvHealth
    current_output_l: float
    current_run_rate_lph: float
    expected_now_l: float
    target_lph: float
    pace_derived: bool
    pace_station_count: int
    pace_gap_l: float
    projected_total_l: float
    shift_target_l: float
    build_pct: float
    scope_packed: int
    total_poured: int
    total_packed: int
    unpacked_wip: int
    packing_enabled: bool
    show_runs_card: bool
    top_pourers: list[TopPourer]
    packing_breakdown: list[PackingBreakdownRow]
    work_orders: list[WorkOrderRow]
