"""Device Gateway, ported from pages/Device_Registry.py - the "find, assign,
put it in analytics" UI: register a machine (whatever protocol it speaks),
point it at the PumpStation it physically sits on, tell it which of its raw
tags mean what. The background gateway process (run_gateway.py) is what
actually polls; this router only edits the devices/device_tag_maps rows it
reads from, exactly as the original page's own docstring says.

Gated by require_device_gateway (api/deps.py): an admin-console user AND the
enable_device_gateway plant setting both have to be true. /meta is the one
exception - it's reachable on require_admin_console alone, specifically so
the frontend can show "the gateway is off, here's where to turn it on"
instead of a bare 403 with no explanation.

test_device_connection does real, synchronous I/O against whatever endpoint
the caller names (device_crud.py; see that module's own research notes) - two
of its six adapters (opcua, mqtt) have no adapter-level connect timeout, so
a bad IP can hang the calling thread far longer than a UI button should ever
wait. Bounded here with a hard wall-clock timeout via a worker thread, same
risk class as a firewall rule silently dropping packets rather than
rejecting them.
"""
import concurrent.futures

from fastapi import APIRouter, Depends, HTTPException

import crud
import device_crud
from api.deps import require_admin_console, require_device_gateway
from api.schemas.devices import (CreateDeviceRequest, DeviceMetaOut, DeviceOut, NetworkHostOut,
                                 OptionOut, ReadingRow, SerialPortOut, TagMapRow,
                                 TestConnectionRequest, TestConnectionResult, UpsertTagMapRequest)
from device_gateway.discovery import guess_local_subnet, list_serial_ports, scan_network
from device_gateway.normalize import CANONICAL_METRICS
from device_gateway.registry import PROTOCOL_LABELS

router = APIRouter(prefix="/devices", tags=["devices"])

TEST_CONNECTION_TIMEOUT_S = 10.0
ROLE_OPTIONS = ["filling_station", "scale", "label_printer", "reactor_sensor", "other"]


def _opt(value):
    """A DataFrame cell as None-or-string, never "nan" - pandas reads a NULL
    text column back as float('nan'), not None, and Pydantic's str | None
    rejects that outright (nan is a float, not a valid string). See
    api/routers/admin.py's _opt / reactors.py's _s for the same trap."""
    if value is None:
        return None
    if isinstance(value, float) and value != value:
        return None
    return str(value)


@router.get("/meta", response_model=DeviceMetaOut)
def meta(user: dict = Depends(require_admin_console)):
    pumps = crud.get_all_pumps_df()
    reactors = crud.get_all_reactors_df()
    return DeviceMetaOut(
        gateway_enabled=bool(crud.get_plant_settings().get("enable_device_gateway", False)),
        protocol_labels=PROTOCOL_LABELS, canonical_metrics=list(CANONICAL_METRICS), role_options=ROLE_OPTIONS,
        pumps=[OptionOut(id=int(r["id"]), name=r["station_name"]) for _, r in pumps.iterrows()] if not pumps.empty else [],
        reactors=[OptionOut(id=int(r["id"]), name=r["reactor_name"]) for _, r in reactors.iterrows()] if not reactors.empty else [],
    )


@router.get("", response_model=list[DeviceOut])
def list_devices(user: dict = Depends(require_device_gateway)):
    df = device_crud.get_devices_df()
    out = []
    for _, r in df.iterrows():
        out.append(DeviceOut(
            id=int(r["id"]), device_name=r["device_name"], device_role=r["device_role"], protocol=r["protocol"],
            assigned_pump=r["assigned_pump"], assigned_reactor=r["assigned_reactor"],
            poll_interval_s=float(r["poll_interval_s"]), is_enabled=bool(r["is_enabled"]), status=r["status"],
            last_seen_at=r["last_seen_at"].isoformat() if r["last_seen_at"] is not None and str(r["last_seen_at"]) != "NaT" else None,
            last_error=r["last_error"] if r["last_error"] and str(r["last_error"]) != "nan" else None,
        ))
    return out


@router.post("", response_model=DeviceOut, status_code=201)
def create_device(body: CreateDeviceRequest, user: dict = Depends(require_device_gateway)):
    if not body.device_name.strip():
        raise HTTPException(status_code=400, detail="Device name is required.")
    new_id = device_crud.create_device(
        device_name=body.device_name, device_role=body.device_role, protocol=body.protocol,
        connection=body.connection, poll_interval_s=body.poll_interval_s,
        pump_station_id=body.pump_station_id, reactor_id=body.reactor_id, notes=body.notes,
    )
    if new_id is None:
        raise HTTPException(status_code=409, detail="A device with that name already exists.")
    df = device_crud.get_devices_df()
    row = df[df["id"] == new_id].iloc[0]
    return DeviceOut(
        id=new_id, device_name=row["device_name"], device_role=row["device_role"], protocol=row["protocol"],
        assigned_pump=row["assigned_pump"], assigned_reactor=row["assigned_reactor"],
        poll_interval_s=float(row["poll_interval_s"]), is_enabled=bool(row["is_enabled"]), status=row["status"],
        last_seen_at=None, last_error=None,
    )


@router.put("/{device_id}/enabled")
def set_enabled(device_id: int, enabled: bool, user: dict = Depends(require_device_gateway)):
    if not device_crud.set_device_enabled(device_id, enabled):
        raise HTTPException(status_code=404, detail="Device not found.")
    return {"ok": True}


@router.delete("/{device_id}")
def delete_device(device_id: int, user: dict = Depends(require_device_gateway)):
    device_crud.delete_device(device_id)
    return {"ok": True}


@router.get("/{device_id}/tags", response_model=list[TagMapRow])
def tags(device_id: int, user: dict = Depends(require_device_gateway)):
    df = device_crud.get_tag_map_df(device_id)
    return [
        TagMapRow(id=int(r["id"]), raw_tag=r["raw_tag"], canonical_metric=r["canonical_metric"],
                 data_type=r["data_type"], scale_factor=float(r["scale_factor"]), unit=_opt(r.get("unit")))
        for _, r in df.iterrows()
    ]


@router.post("/{device_id}/tags")
def save_tag(device_id: int, body: UpsertTagMapRequest, user: dict = Depends(require_device_gateway)):
    if not body.raw_tag.strip():
        raise HTTPException(status_code=400, detail="Raw tag can't be empty.")
    device_crud.upsert_tag_map_row(device_id, body.raw_tag.strip(), body.canonical_metric,
                                   body.data_type, body.scale_factor, body.unit)
    return {"ok": True}


@router.delete("/tags/{tag_id}")
def delete_tag(tag_id: int, user: dict = Depends(require_device_gateway)):
    device_crud.delete_tag_map_row(tag_id)
    return {"ok": True}


@router.get("/{device_id}/readings", response_model=list[ReadingRow])
def readings(device_id: int, hours: int = 4, user: dict = Depends(require_device_gateway)):
    df = device_crud.get_recent_readings_df(device_id, hours=hours)
    return [
        ReadingRow(
            timestamp=r["timestamp"].isoformat(), metric=r["metric"],
            value_numeric=float(r["value_numeric"]) if r["value_numeric"] is not None and str(r["value_numeric"]) != "nan" else None,
            value_text=r["value_text"] if r["value_text"] and str(r["value_text"]) != "nan" else None,
        )
        for _, r in df.iterrows()
    ]


@router.post("/test-connection", response_model=TestConnectionResult)
def test_connection(body: TestConnectionRequest, user: dict = Depends(require_device_gateway)):
    temp_tag_map = [{"raw_tag": t, "canonical_metric": t, "data_type": "float", "scale_factor": 1.0}
                    for t in body.probe_tags]
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(device_crud.test_device_connection, body.protocol, body.connection, temp_tag_map)
        try:
            result = future.result(timeout=TEST_CONNECTION_TIMEOUT_S)
        except concurrent.futures.TimeoutError:
            return TestConnectionResult(ok=False, error=f"Timed out after {TEST_CONNECTION_TIMEOUT_S:.0f}s waiting for a response.")
    if "error" in result:
        return TestConnectionResult(ok=False, error=result["error"])
    return TestConnectionResult(ok=True, raw=result.get("raw", {}))


@router.get("/discovery/serial-ports", response_model=list[SerialPortOut])
def serial_ports(user: dict = Depends(require_device_gateway)):
    return [SerialPortOut(port=p["port"], description=p.get("description"), manufacturer=p.get("manufacturer"))
           for p in list_serial_ports()]


@router.get("/discovery/subnet")
def subnet(user: dict = Depends(require_device_gateway)):
    return {"subnet": guess_local_subnet()}


@router.get("/discovery/scan", response_model=list[NetworkHostOut])
def scan(subnet: str, user: dict = Depends(require_device_gateway)):
    try:
        hosts = scan_network(subnet)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return [NetworkHostOut(ip=h["ip"], hostname=h.get("hostname"), open_ports=h["open_ports"],
                           guessed_protocol=h.get("guessed_protocol"))
           for h in hosts]
