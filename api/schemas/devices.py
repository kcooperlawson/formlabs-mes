from typing import Any

from pydantic import BaseModel


class DeviceOut(BaseModel):
    id: int
    device_name: str
    device_role: str
    protocol: str
    assigned_pump: str
    assigned_reactor: str
    poll_interval_s: float
    is_enabled: bool
    # What to show, not just what the gateway last wrote: "Not reporting" is
    # layered on when there's no sign anything is still reading this device
    # (device_crud.effective_status).
    status: str
    last_seen_at: str | None
    seconds_since_seen: float | None = None
    last_error: str | None


class CreateDeviceRequest(BaseModel):
    device_name: str
    device_role: str
    protocol: str
    connection: dict
    poll_interval_s: float = 5.0
    pump_station_id: int | None = None
    reactor_id: int | None = None
    notes: str = ""


class TagMapRow(BaseModel):
    id: int
    raw_tag: str
    canonical_metric: str
    data_type: str
    scale_factor: float
    unit: str | None


class UpsertTagMapRequest(BaseModel):
    raw_tag: str
    canonical_metric: str
    data_type: str = "float"
    scale_factor: float = 1.0
    unit: str = ""


class ReadingRow(BaseModel):
    timestamp: str
    metric: str
    value_numeric: float | None
    value_text: str | None


class TestConnectionRequest(BaseModel):
    protocol: str
    connection: dict
    probe_tags: list[str] = []


class TestConnectionResult(BaseModel):
    ok: bool
    raw: dict = {}
    error: str | None = None


class SerialPortOut(BaseModel):
    port: str
    description: str | None
    manufacturer: str | None


class NetworkHostOut(BaseModel):
    ip: str
    hostname: str | None
    open_ports: list[int]
    guessed_protocol: str | None


class OptionOut(BaseModel):
    id: int
    name: str


class DeviceMetaOut(BaseModel):
    gateway_enabled: bool
    server_hostname: str
    protocol_labels: dict[str, str]
    canonical_metrics: list[str]
    role_options: list[str]
    pumps: list[OptionOut]
    reactors: list[OptionOut]


class GatewayNodeOut(BaseModel):
    hostname: str
    ip_address: str | None
    app_version: str | None
    started_at: str | None
    last_heartbeat_at: str | None
    seconds_since_heartbeat: float | None
    online: bool


class GatewayJobRequest(BaseModel):
    kind: str
    params: dict = {}


class GatewayJobCreated(BaseModel):
    id: int


class GatewayJobOut(BaseModel):
    id: int
    target_host: str
    kind: str
    status: str
    result: Any = None
    error: str | None = None
