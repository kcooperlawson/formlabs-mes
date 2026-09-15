from pydantic import BaseModel, Field


class PackingSubmitRequest(BaseModel):
    cartridge_type: str  # resolved code, e.g. "V2"
    resin: str
    lot_number: str
    units_packed: int = Field(ge=1)
    notes: str = ""
    as_operator: str | None = None
