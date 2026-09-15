from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    pin: str
    remember: bool = True


class RegisterRequest(BaseModel):
    full_name: str
    email: str
    username: str
    pin: str
    role: str  # "operator" | "packer" - self-registration can never grant anything above these
    shift: str


class PlantModeOut(BaseModel):
    simple_mode: bool


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    role: str
    shift: str | None = None
    preferred_theme: str | None = None
    avatar_filename: str | None = None
