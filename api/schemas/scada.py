from pydantic import BaseModel


class HealthOut(BaseModel):
    state: str
    is_alarm: bool
    is_warning: bool
    message: str


class TrajectoryOut(BaseModel):
    is_live: bool
    active_shift_name: str
    elapsed_net: float
    remaining_hours: float
    shift_pct: float
    expected_display: str
    projected_total: float
    pace_variance_l: float
    oee_pct: float
    status_badge: str
    next_shift_label: str


class LeaderboardEntry(BaseModel):
    operator: str
    velocity_lh: float


class CartTypeCount(BaseModel):
    cartridge_type: str
    units: int


class PouringOut(BaseModel):
    liters_output: float
    resin_mass_kg: float
    run_velocity_lh: float
    target_rate_lh: float
    yield_pct: float
    total_scrap: int
    cart_type_counts: list[CartTypeCount]
    trajectory: TrajectoryOut | None = None
    leaderboard: list[LeaderboardEntry] = []


class PackedByResinLot(BaseModel):
    resin: str
    lot_number: str
    units: int
    skids: float


class PackingOut(BaseModel):
    total_packed: int
    total_skids_est: float
    pack_velocity_uh: float
    unpacked_wip: int
    by_resin_lot: list[PackedByResinLot] = []


class LogRow(BaseModel):
    timestamp: str
    date: str
    log_type: str
    operator_name: str
    pump_station: str
    cartridge_type: str
    resin_type: str
    lot_number: str = ""
    bottles_filled: int
    scrap_empty: int
    scrap_filled: int
    notes: str


class ScadaFilters(BaseModel):
    pumps: list[str]
    resins: list[str]
    operators: list[str]
    shifts: list[str]
    dates: list[str]


class ScadaOverviewOut(BaseModel):
    health: HealthOut
    headline_liters: float
    headline_pace_variance_l: float
    headline_is_live: bool
    filters: ScadaFilters
    show_pouring: bool
    show_packing: bool
    pouring: PouringOut | None = None
    packing: PackingOut | None = None
    log_stream: list[LogRow] = []
    log_stream_title: str
