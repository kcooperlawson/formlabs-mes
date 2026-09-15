from pydantic import BaseModel


class ResinColor(BaseModel):
    bg: str
    fg: str
    border: str


class ResinSpecOut(BaseModel):
    cartridge_type: str
    resin_name: str
    target_g: float
    min_g: float
    max_g: float
    target_kg: float
    units_per_skid: int
    color: ResinColor


class PlantSettingsPublic(BaseModel):
    simple_mode: bool
    enable_bulk_pour: bool
    enable_packing: bool
    enable_device_gateway: bool
    pump_form_url: str
    pump_form_label: str


class LastPicksOut(BaseModel):
    station: str
    cartridge: str
    resin: str
