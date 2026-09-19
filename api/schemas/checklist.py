from pydantic import BaseModel


class ChecklistStatus(BaseModel):
    checklist_done: bool
    cleanliness_done_today: bool


class VesselOption(BaseModel):
    value: str  # reactor_name - sent back on /submit as vessel_reactor_name
    label: str  # shared._vessel_label(v)


class VesselOptionsOut(BaseModel):
    has_vessel: bool
    options: list[VesselOption]


class ChecklistSubmitRequest(BaseModel):
    station: str
    shift: str
    qr_checked: bool
    materials_checked: bool
    vessel_reactor_name: str | None = None


class MarkAlreadyDoneRequest(BaseModel):
    station: str
    shift: str
    already_who: str


class ComplianceRow(BaseModel):
    """One operator at one pump on one shift, and which of their checks are
    on record. Times are ISO with a UTC offset, or null for "not done"."""
    operator_name: str
    pump_station: str
    shift: str
    poured: int
    checklist_at: str | None
    start_audit_at: str | None
    transfer_audit_at: str | None
    end_audit_at: str | None
    start_expected: bool
    transfer_expected: bool
    end_expected: bool
    complete: bool


class ComplianceOut(BaseModel):
    date: str
    rows: list[ComplianceRow]
    # Only a manager sees other people's rows; an operator sees their own.
    scope: str
