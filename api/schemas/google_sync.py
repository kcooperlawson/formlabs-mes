from typing import Any

from pydantic import BaseModel


class SheetTargetOut(BaseModel):
    id: int
    name: str
    webhook_url: str
    owner_user_id: int | None
    owner_name: str
    is_shared: bool
    label: str
    last_sync_text: str
    editable: bool


class AddTargetRequest(BaseModel):
    name: str
    url: str
    is_shared: bool = False


class UpdateTargetRequest(BaseModel):
    name: str | None = None
    webhook_url: str | None = None
    is_shared: bool | None = None


class ClassifyUrlOut(BaseModel):
    kind: str
    url: str
    ok: bool
    message: str


class TestResult(BaseModel):
    ok: bool
    message: str


class ExportPreviewOut(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    row_count: int


class PushRequest(BaseModel):
    target_id: int
    export_mode: str
    horizon: str
    columns: list[str]


class PushResult(BaseModel):
    ok: bool
    message: str
    rows: int | None = None
    tab: str | None = None
    sheet: str | None = None
    url: str | None = None
