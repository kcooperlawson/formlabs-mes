from pydantic import BaseModel


class FloorUserOut(BaseModel):
    id: int
    full_name: str
    username: str
    role: str
    shift: str


class ProvisionRequest(BaseModel):
    full_name: str
    email: str
    username: str
    pin: str
    role: str  # "operator" | "packer" - self-registration-style pages never grant above this
    shift: str
    target_lph: float = 400.0


class ResetPinRequest(BaseModel):
    user_id: int
    new_pin: str
