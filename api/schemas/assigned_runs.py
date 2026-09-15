from pydantic import BaseModel


class ReactorOption(BaseModel):
    reactor_name: str
    max_capacity_l: int


class RunOptions(BaseModel):
    reactors: list[ReactorOption]
    pumps: list[str]
    operators: list[str]
    packers: list[str]
    pump_count: int
    enable_packing: bool


class AssignedRunOut(BaseModel):
    id: int
    run_type: str
    status: str
    reactor_id: str
    reactor_size_l: int
    resin_type: str
    resin_color: str
    cartridge_type: str
    target_units: int
    current_units: int
    assigned_operator: str
    pump_station: str
    lot_number: str
    notes: str
    created_at: str


class RunTotals(BaseModel):
    total_target: int
    total_actual: int
    fleet_pct: float
    active_count: int
    queued_count: int
    done_count: int
    pumps_configured: int
    pumps_in_use: int
    active_operators_count: int


class AssignedRunsOut(BaseModel):
    runs: list[AssignedRunOut]
    totals: RunTotals


class CreateRunRequest(BaseModel):
    run_type: str
    reactor_id: str
    reactor_size_l: int
    cartridge_type: str
    resin_type: str
    target_units: int
    assigned_pump: str
    assigned_operator: str
    lot_number: str
    notes: str = ""
    status: str = "Active"


class ProgressRequest(BaseModel):
    delta: int


class StatusRequest(BaseModel):
    status: str


class CompleteRequest(BaseModel):
    final_units: int
