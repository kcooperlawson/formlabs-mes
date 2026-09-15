from pydantic import BaseModel


class UpdateCredentialsRequest(BaseModel):
    full_name: str
    username: str
    pin: str = ""  # blank means "leave unchanged" - see crud.update_user_credentials


class UpdateThemeRequest(BaseModel):
    theme: str


class SubmitFeedbackRequest(BaseModel):
    category: str
    suggestion: str


class MyFeedbackOut(BaseModel):
    id: int
    timestamp: str | None
    category: str
    suggestion: str
    status: str
    admin_notes: str | None
