from pydantic import BaseModel


class NoteOut(BaseModel):
    sender_name: str
    message: str
    timestamp: str  # ISO 8601
    is_manager_reply: bool
    avatar_data_uri: str | None = None


class NoteSubmitRequest(BaseModel):
    message: str
    as_operator: str | None = None
