from pydantic import BaseModel


class OperatorThreadSummary(BaseModel):
    name: str
    has_written: bool


class FloorReplyRequest(BaseModel):
    operator_name: str
    message: str
