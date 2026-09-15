from pydantic import BaseModel


class VesselRef(BaseModel):
    reactor_name: str
    tag: str  # asset_tag, or reactor_name itself when there's no tag
    bay_marker: str | None = None


class VesselChoice(BaseModel):
    value: str  # reactor_name
    label: str  # shared._vessel_label(v)


class BatchInfo(BaseModel):
    id: int
    qc_result: str
    qc_open: bool
    hours_in_reactor: float | None = None


class ReactorLookupOut(BaseModel):
    """One response for every branch pouring_tab.py's inline vessel block
    used to render (see api/routers/pouring.py for the branch-by-branch
    mapping) - `status` says which, the rest of the fields are populated
    only for the branch they belong to."""
    status: str  # "blank" | "changeover" | "no_vessel" | "ambiguous" | "matched"
    vessel: VesselRef | None = None
    current_resin: str | None = None            # status == "changeover"
    options: list[VesselChoice] = []            # status == "no_vessel"
    vessel_names: list[str] = []                # status == "ambiguous"
    batch: BatchInfo | None = None               # status == "matched", if a filling is open
    can_mark_empty: bool = False                 # status == "matched"


class ChangeoverRequest(BaseModel):
    reactor_name: str
    new_resin: str
    station: str
    shift: str
    as_operator: str | None = None  # manager/admin Debug Mode override, see api.deps.resolve_operator_name


class LinkVesselRequest(BaseModel):
    reactor_name: str
    station: str


class MarkEmptyRequest(BaseModel):
    reactor_name: str
    as_operator: str | None = None


class FastPathInfo(BaseModel):
    since: str  # ISO timestamp of the last full/fast verification
    by: str
    entered_masked: str  # what THEY typed last time - never the hidden expected value


class LotGateOut(BaseModel):
    gate_applies: bool
    noun: str
    field_label: str
    where_hint: str
    still_reads_label: str
    expected_is_real: bool
    auto_lot: str  # only meaningful when gate_applies is False (an editable default)
    matched_run: bool
    fast_path: FastPathInfo | None = None


class LotCheckOut(BaseModel):
    result: str  # "verified" | "recorded" | "mismatch"


class BulkPreviewRequest(BaseModel):
    resin: str
    station: str
    containers: int = 1
    amount_each: float = 0.0
    unit: str = "L"
    off_tank: bool = False
    note: str = ""


class BulkPreviewOut(BaseModel):
    litres: float
    description: str
    blocked: bool
    message: str


class PourSubmitResponse(BaseModel):
    ok: bool
    log_id: int | None = None
    matched_run: bool
    weight_icon: str = ""
    weight_message: str = ""
    messages: list[str] = []
    landed: str


class UndoRequest(BaseModel):
    log_id: int
    as_operator: str | None = None


class UndoResponse(BaseModel):
    ok: bool
    message: str
