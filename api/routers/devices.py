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
import ipaddress
import socket
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException

import crud
import device_crud
from api.deps import require_admin_console, require_device_gateway
from api.schemas.devices import (CreateDeviceRequest, DeviceMetaOut, DeviceOut, GatewayJobCreated,
                                 GatewayJobOut, GatewayJobRequest, GatewayNodeOut, NetworkHostOut,
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


def _utc_iso(value):
    """A stored timestamp as ISO-8601 with its UTC offset.

    Everything here is stored as naive UTC. Sent without an offset, the
    browser reads it as LOCAL time - on Eastern time that put every
    timestamp four hours in the future, so "last seen" said "just now" for
    four hours after a gateway stopped, and Recent Readings showed the wrong
    hour. With the offset the browser converts it properly."""
    if value is None or str(value) in ("NaT", "nan"):
        return None
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _num(value):
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if value != value else value


@router.get("/meta", response_model=DeviceMetaOut)
def meta(user: dict = Depends(require_admin_console)):
    pumps = crud.get_all_pumps_df()
    reactors = crud.get_all_reactors_df()
    return DeviceMetaOut(
        gateway_enabled=bool(crud.get_plant_settings().get("enable_device_gateway", False)),
        server_hostname=socket.gethostname(),
        protocol_labels=PROTOCOL_LABELS, canonical_metrics=list(CANONICAL_METRICS), role_options=ROLE_OPTIONS,
        pumps=[OptionOut(id=int(r["id"]), name=r["station_name"]) for _, r in pumps.iterrows()] if not pumps.empty else [],
        reactors=[OptionOut(id=int(r["id"]), name=r["reactor_name"]) for _, r in reactors.iterrows()] if not reactors.empty else [],
    )


@router.get("", response_model=list[DeviceOut])
def list_devices(user: dict = Depends(require_device_gateway)):
    df = device_crud.get_devices_df()
    gateways = device_crud.get_gateway_nodes()
    out = []
    for _, r in df.iterrows():
        stored = {
            "status": r["status"], "is_enabled": bool(r["is_enabled"]),
            "poll_interval_s": float(r["poll_interval_s"] or 5.0),
            "seconds_since_seen": _num(r["seconds_since_seen"]),
            "last_error": r["last_error"] if r["last_error"] and str(r["last_error"]) != "nan" else None,
        }
        status, error = device_crud.effective_status(stored, gateways)
        out.append(DeviceOut(
            id=int(r["id"]), device_name=r["device_name"], device_role=r["device_role"], protocol=r["protocol"],
            assigned_pump=r["assigned_pump"], assigned_reactor=r["assigned_reactor"],
            poll_interval_s=stored["poll_interval_s"], is_enabled=stored["is_enabled"], status=status,
            last_seen_at=_utc_iso(r["last_seen_at"]), seconds_since_seen=stored["seconds_since_seen"],
            last_error=error,
        ))
    return out


@router.get("/gateways", response_model=list[GatewayNodeOut])
def gateways(user: dict = Depends(require_device_gateway)):
    """Every PC running run_gateway.py that has checked in, newest first."""
    return [
        GatewayNodeOut(
            hostname=g["hostname"], ip_address=g["ip_address"], app_version=g["app_version"],
            started_at=_utc_iso(g["started_at"]), last_heartbeat_at=_utc_iso(g["last_heartbeat_at"]),
            seconds_since_heartbeat=g["seconds_since_heartbeat"], online=g["online"],
        )
        for g in device_crud.get_gateway_nodes()
    ]


@router.post("/gateways/{hostname}/jobs", response_model=GatewayJobCreated, status_code=201)
def create_gateway_job(hostname: str, body: GatewayJobRequest, user: dict = Depends(require_device_gateway)):
    """Ask the gateway on `hostname` to run Find Devices / Test Connection
    where the hardware is, instead of on this server. The page polls
    /gateway-jobs/{id} for the answer."""
    if body.kind not in device_crud.GATEWAY_JOB_KINDS:
        raise HTTPException(status_code=400, detail=f"Unknown job {body.kind!r}.")
    if not any(g["hostname"] == hostname for g in device_crud.get_gateway_nodes()):
        raise HTTPException(status_code=404, detail=f"No gateway called {hostname!r} has ever checked in.")
    params = dict(body.params or {})
    if body.kind == "scan":
        try:
            ipaddress.ip_network(str(params.get("subnet") or ""), strict=False)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"{params.get('subnet')!r} isn't a subnet like 192.168.0.0/24.")
    if body.kind == "test_connection":
        params = {"protocol": str(params.get("protocol") or ""), "connection": params.get("connection") or {},
                  "probe_tags": [str(t) for t in (params.get("probe_tags") or [])]}
    job_id = device_crud.create_gateway_job(hostname, body.kind, params, created_by=user.get("username", ""))
    return GatewayJobCreated(id=job_id)


@router.get("/gateway-jobs/{job_id}", response_model=GatewayJobOut)
def gateway_job(job_id: int, user: dict = Depends(require_device_gateway)):
    job = device_crud.get_gateway_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return GatewayJobOut(**job)


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
            timestamp=_utc_iso(r["timestamp"]), metric=r["metric"],
            value_numeric=float(r["value_numeric"]) if r["value_numeric"] is not None and str(r["value_numeric"]) != "nan" else None,
            value_text=r["value_text"] if r["value_text"] and str(r["value_text"]) != "nan" else None,
        )
        for _, r in df.iterrows()
    ]


@router.post("/test-connection", response_model=TestConnectionResult)
def test_connection(body: TestConnectionRequest, user: dict = Depends(require_device_gateway)):
    temp_tag_map = device_crud.probe_tag_map(body.protocol, body.probe_tags)
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
