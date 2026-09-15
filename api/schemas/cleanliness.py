from pydantic import BaseModel


class CleanlinessStats(BaseModel):
    total_audits: int
    start_checks: int
    end_checks: int
    transfers: int
    spills: int


class CleanlinessAuditOut(BaseModel):
    id: int
    audit_type: str
    pump_station: str
    operator_name: str
    timestamp: str
    notes: str
    is_spill: bool
    photos: list[str] = []  # filenames; main photo first, then extras
