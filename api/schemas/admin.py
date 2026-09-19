from pydantic import BaseModel


# --- roster ------------------------------------------------------------
class UserOut(BaseModel):
    id: int
    full_name: str
    username: str
    email: str | None
    role: str
    shift: str | None
    target_lph: float | None
    is_locked: bool
    locked_minutes_left: int | None
    failed_login_attempts: int


class CreateUserRequest(BaseModel):
    full_name: str
    email: str
    username: str
    pin: str
    role: str
    shift: str
    target_lph: float = 400.0


class UpdateRoleShiftRequest(BaseModel):
    role: str
    shift: str


class ResetPinRequest(BaseModel):
    pin: str


# --- abilities -----------------------------------------------------------
class AbilityInfo(BaseModel):
    key: str
    label: str
    help: str
    status: str  # "role" | "granted" | ""
    can_grant: bool  # whether the CURRENT admin holds this ability themselves


class AbilityHistoryEntry(BaseModel):
    ability: str
    label: str
    granted_by: str | None
    granted_at: str | None
    revoked_by: str | None
    revoked_at: str | None
    active: bool


class UserAbilitiesOut(BaseModel):
    user_id: int
    full_name: str
    role: str
    abilities: list[AbilityInfo]
    history: list[AbilityHistoryEntry]


# --- crash reports ---------------------------------------------------------
class ErrorReportOut(BaseModel):
    id: int
    ref_code: str
    occurred_at: str | None
    last_seen_at: str | None
    page: str | None
    user_name: str | None
    user_role: str | None
    app_version: str | None
    error_type: str | None
    message: str | None
    traceback: str | None
    hits: int
    resolved: bool
    resolved_at: str | None
    resolved_by: str | None
    note: str | None


class ResolveErrorRequest(BaseModel):
    note: str = ""


# --- suggestions -----------------------------------------------------------
class SuggestionOut(BaseModel):
    id: int
    timestamp: str | None
    user_name: str
    user_role: str
    category: str
    suggestion: str
    status: str
    admin_notes: str | None
    avatar_data_uri: str | None


class UpdateSuggestionRequest(BaseModel):
    status: str
    admin_notes: str = ""


# --- database utilities ---------------------------------------------------
class WipStatusOut(BaseModel):
    poured_today: int
    packed_today: int
    wip: int


class BackupStatusOut(BaseModel):
    state: str
    count: int
    newest: str | None
    age_hours: float | None
    message: str
    due_after_hours: float
    keep_backups: int


class CreateBackupOut(BaseModel):
    filename: str


class RestoreBackupRequest(BaseModel):
    filename: str


# --- plant configuration ---------------------------------------------------
class PlantSettingsOut(BaseModel):
    shift_1_start: str
    shift_1_hours: float
    shift_1_break_mins: int
    shift_2_start: str
    shift_2_hours: float
    shift_2_break_mins: int
    shift_count: int
    target_lph: float
    yield_target_pct: float
    enable_packing: bool
    enable_bulk_pour: bool
    enable_device_gateway: bool
    operating_days: str
    operating_days_desc: str
    simple_mode: bool
    pump_form_url: str
    pump_form_label: str


class UpdatePlantSettingsRequest(BaseModel):
    shift_1_start: str
    shift_1_hours: float
    shift_1_break_mins: int
    shift_2_start: str
    shift_2_hours: float
    shift_2_break_mins: int
    shift_count: int
    target_lph: float
    yield_target_pct: float
    enable_packing: bool
    enable_bulk_pour: bool
    enable_device_gateway: bool
    operating_days: list[int]
    use_work_orders: bool
    pump_form_url: str
    pump_form_label: str


class UpdatePlantSettingsResult(BaseModel):
    saved: PlantSettingsOut
    pump_form_warning: str | None
    orders_off_warning: str | None
    no_admin_warning: str | None


class PumpOut(BaseModel):
    id: int
    station_name: str
    status: str
    # "piston_diaphragm" | "electric_motor" | None for one nobody has labelled
    pump_type: str | None
    pump_type_label: str | None
    target_lph: float | None
    effective_lph: float
    measured_median_lph: float | None
    measured_samples: int | None


class AddPumpRequest(BaseModel):
    station_name: str
    pump_type: str = ""


class SetPumpTypeRequest(BaseModel):
    pump_type: str = ""


class SetPumpRateRequest(BaseModel):
    target_lph: float


class AddDowntimeReasonRequest(BaseModel):
    reason_name: str
