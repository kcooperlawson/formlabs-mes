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
