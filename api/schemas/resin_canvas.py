from pydantic import BaseModel


class ResinCanvasRow(BaseModel):
    id: int
    cartridge_type: str
    sku: str
    resin_code: str
    resin_name: str
    actual_spec_g: float
    min_weight_g: float
    max_weight_g: float
    target_kg: float
    multiplier: float
    lifetime_months: str
    color: str


class AddResinRequest(BaseModel):
    cartridge_type: str
    sku: str
    resin_code: str
    resin_name: str
    actual_spec_g: float
    min_weight_g: float
    max_weight_g: float
    color_tag: str | None = None


class UpdateResinRequest(BaseModel):
    actual_spec_g: float
    min_weight_g: float
    max_weight_g: float
    color_tag: str
