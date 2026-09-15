from pydantic import BaseModel, Field


class DowntimeSubmitRequest(BaseModel):
    station: str
    reason: str
    duration_min: int = Field(ge=1, le=240)
    notes: str = ""
    as_operator: str | None = None
