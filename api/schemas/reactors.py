from pydantic import BaseModel, Field


class BatchInfo(BaseModel):
    hours_in_reactor: float | None = None
    qc_result: str
    qc_open: bool
    hours_at_qc: float | None = None


class ReactorCard(BaseModel):
    id: int
    reactor_name: str
    capacity_l: float
    asset_tag: str
    bay_marker: str
    current_resin: str | None
    assigned_pump: str | None
    is_idle: bool
    remaining_l: float
    remaining_kg: float
    fill_pct: float
    lot: str
    svg: str
    batch: BatchInfo | None = None
    can_mark_empty: bool


class VesselTypeOption(BaseModel):
    value: str
    label: str
    help: str


class ManageOptionsOut(BaseModel):
    vessel_types: list[VesselTypeOption]
    resins: list[str]
    pumps: list[str]
    bulk_enabled: bool


class ManageReactorRow(BaseModel):
    id: int
    reactor_name: str
    capacity_l: float
    vessel_type: str
    asset_tag: str
    bay_marker: str
    assigned_pump: str
    current_resin: str


class AddReactorRequest(BaseModel):
    reactor_name: str
    max_capacity_l: float = Field(gt=0)
    vessel_type: str = ""
    asset_tag: str = ""
    bay_marker: str = ""


class UpdateReactorRequest(BaseModel):
    vessel_type: str
    asset_tag: str = ""
    bay_marker: str = ""
    assigned_pump: str = ""   # "" means "not set"
    current_resin: str = ""  # "" means "not set"


class BulkCandidate(BaseModel):
    id: int
    reactor_name: str
    label: str
    current_resin: str


class DrawInfo(BaseModel):
    capacity_l: float
    current_resin: str
    lot: str
    remaining_l: float
    density_kg_l: float


class BulkPourRequest(BaseModel):
    containers: int = Field(ge=1, le=99)
    amount_each: float = Field(ge=0)
    unit: str = "L"
    note: str = ""


class MarkEmptyOut(BaseModel):
    ok: bool
