"""
device_crud.py - CRUD for the Device Gateway, in the same shape as crud.py
(same ScopedSession-per-call pattern) so it drops into database.py's
facade with one import line and every existing page style still applies.

    # database.py
    from device_models import Device, DeviceTagMap, DeviceReading
    from device_crud import *
"""
import json
from datetime import datetime, timedelta

import pandas as pd
from sqlalchemy import desc, func

from db_core import ScopedSession
from models import PumpStation, Reactor
from device_models import Device, DeviceTagMap, DeviceReading, GatewayJob, GatewayNode
from app_logger import logger
from gateway_crypto import encrypt_connection, decrypt_connection, decrypt_connection_strict


def db_utc_now():
    """The database server's clock, in UTC, as a SQL expression.

    Every "how long ago" this module answers compares two times from the same
    clock. The gateway PC and the MES PC are different machines, and a floor
    PC that is off the domain can drift by minutes; comparing its clock with
    the server's would call a healthy gateway offline."""
    return func.timezone("utc", func.now())


def _seconds_since(column):
    return func.extract("epoch", db_utc_now() - column)


# --- DEVICES ---------------------------------------------------------------

def get_devices_df() -> pd.DataFrame:
    """One row per device, with the pump station / reactor it's assigned
    to resolved to a readable name (not just the FK id) for display on the
    admin page."""
    session = ScopedSession()
    try:
        rows = (
            session.query(Device, PumpStation.station_name, Reactor.reactor_name,
                          _seconds_since(Device.last_seen_at))
            .outerjoin(PumpStation, Device.pump_station_id == PumpStation.id)
            .outerjoin(Reactor, Device.reactor_id == Reactor.id)
            .order_by(Device.device_name)
            .all()
        )
        records = []
        for device, pump_name, reactor_name, seen_s in rows:
            records.append({
                "id": device.id,
                "device_name": device.device_name,
                "device_role": device.device_role,
                "protocol": device.protocol,
                "assigned_pump": pump_name or "—",
                "assigned_reactor": reactor_name or "—",
                "poll_interval_s": device.poll_interval_s,
                "is_enabled": device.is_enabled,
                "status": device.status,
                "last_seen_at": device.last_seen_at,
                "seconds_since_seen": float(seen_s) if seen_s is not None else None,
                "last_error": device.last_error,
            })
        return pd.DataFrame(records)
    finally:
        session.close()


def get_device_dict(device_id: int) -> dict | None:
    session = ScopedSession()
    try:
        device = session.get(Device, device_id)
        if not device:
            return None
        return {
            "id": device.id,
            "device_name": device.device_name,
            "device_role": device.device_role,
            "protocol": device.protocol,
            "connection": decrypt_connection(device.connection_json),
            "poll_interval_s": device.poll_interval_s,
            "is_enabled": device.is_enabled,
            "pump_station_id": device.pump_station_id,
            "reactor_id": device.reactor_id,
            "status": device.status,
            "last_seen_at": device.last_seen_at,
            "last_error": device.last_error,
            "notes": device.notes,
        }
    finally:
        session.close()


# The simulator adapter (device_gateway/adapters/simulator.py) always
# reports raw tags already named after the canonical metric they mean, so
# a demo device can go live with zero manual tag-mapping - this is what
# fills that in automatically the moment one is created, keyed by the same
# "sim_profile" the adapter itself reads out of connection_json.
_SIMULATOR_TAGS = {
    "pump": [
        ("units_poured_delta", "units_poured_delta", "float"),
        ("weight_g", "weight_g", "float"),
        ("machine_state", "machine_state", "string"),
        ("fault_code", "fault_code", "string"),
    ],
    "scale": [
        ("weight_g", "weight_g", "float"),
    ],
}


def create_device(device_name: str, device_role: str, protocol: str, connection: dict,
                   poll_interval_s: float = 5.0, pump_station_id: int | None = None,
                   reactor_id: int | None = None, notes: str = "", is_enabled: bool = True) -> int | None:
    session = ScopedSession()
    try:
        if session.query(Device).filter(Device.device_name == device_name.strip()).first():
            return None
        device = Device(
            device_name=device_name.strip(), device_role=device_role, protocol=protocol,
            connection_json=encrypt_connection(connection), poll_interval_s=poll_interval_s,
            pump_station_id=pump_station_id, reactor_id=reactor_id, notes=notes,
            is_enabled=is_enabled, status="Unknown",
        )
        session.add(device)

        if protocol == "simulator":
            session.flush()  # need device.id before the tag map rows below can reference it
            profile = str((connection or {}).get("sim_profile") or "pump").lower()
            for raw_tag, canonical_metric, data_type in _SIMULATOR_TAGS.get(profile, _SIMULATOR_TAGS["pump"]):
                session.add(DeviceTagMap(device_id=device.id, raw_tag=raw_tag, canonical_metric=canonical_metric,
                                         data_type=data_type, scale_factor=1.0))

        session.commit()
        return device.id
    except Exception:
        session.rollback()
        logger.exception(f"create_device({device_name!r}) failed")
        return None
    finally:
        session.close()


def update_device(device_id: int, **fields) -> bool:
    """fields may include any of: device_name, device_role, protocol,
    connection (dict, gets json-encoded), poll_interval_s, pump_station_id,
    reactor_id, notes, is_enabled."""
    session = ScopedSession()
    try:
        device = session.get(Device, device_id)
        if not device:
            return False
        if "connection" in fields:
            fields["connection_json"] = encrypt_connection(fields.pop("connection"))
        for key, value in fields.items():
            if hasattr(device, key):
                setattr(device, key, value)
        session.commit()
        return True
    except Exception:
        session.rollback()
        logger.exception(f"update_device({device_id}) failed")
        return False
    finally:
        session.close()


def set_device_enabled(device_id: int, enabled: bool) -> bool:
    return update_device(device_id, is_enabled=enabled)


def delete_device(device_id: int) -> bool:
    session = ScopedSession()
    try:
        device = session.get(Device, device_id)
        if device:
            session.delete(device)  # cascades to device_tag_maps / device_readings (ondelete="CASCADE")
            session.commit()
        return True
    except Exception:
        session.rollback()
        logger.exception(f"delete_device({device_id}) failed")
        return False
    finally:
        session.close()


# --- TAG MAP -----------------------------------------------------------------

def get_tag_map_df(device_id: int) -> pd.DataFrame:
    session = ScopedSession()
    try:
        rows = session.query(DeviceTagMap).filter(DeviceTagMap.device_id == device_id).all()
        return pd.DataFrame([{
            "id": t.id, "raw_tag": t.raw_tag, "canonical_metric": t.canonical_metric,
            "data_type": t.data_type, "scale_factor": t.scale_factor, "unit": t.unit,
        } for t in rows])
    finally:
        session.close()


def get_tag_map_dicts(device_id: int) -> list:
    session = ScopedSession()
    try:
        rows = session.query(DeviceTagMap).filter(DeviceTagMap.device_id == device_id).all()
        return [{
            "raw_tag": t.raw_tag, "canonical_metric": t.canonical_metric,
            "data_type": t.data_type or "float",
            "scale_factor": t.scale_factor if t.scale_factor is not None else 1.0,
        } for t in rows]
    finally:
        session.close()


def upsert_tag_map_row(device_id: int, raw_tag: str, canonical_metric: str,
                        data_type: str = "float", scale_factor: float = 1.0,
                        unit: str = "") -> bool:
    session = ScopedSession()
    try:
        row = session.query(DeviceTagMap).filter(
            DeviceTagMap.device_id == device_id, DeviceTagMap.raw_tag == raw_tag
        ).first()
        if row:
            row.canonical_metric = canonical_metric
            row.data_type = data_type
            row.scale_factor = scale_factor
            row.unit = unit or None
        else:
            session.add(DeviceTagMap(
                device_id=device_id, raw_tag=raw_tag, canonical_metric=canonical_metric,
                data_type=data_type, scale_factor=scale_factor, unit=unit or None,
            ))
        session.commit()
        return True
    except Exception:
        session.rollback()
        logger.exception(f"upsert_tag_map_row(device_id={device_id}, raw_tag={raw_tag!r}) failed")
        return False
    finally:
        session.close()


def delete_tag_map_row(tag_id: int) -> bool:
    session = ScopedSession()
    try:
        row = session.get(DeviceTagMap, tag_id)
        if row:
            session.delete(row)
            session.commit()
        return True
    finally:
        session.close()


# --- READINGS ------------------------------------------------------------

def get_recent_readings_df(device_id: int, hours: int = 4, limit: int = 500) -> pd.DataFrame:
    session = ScopedSession()
    try:
        since = datetime.utcnow() - timedelta(hours=hours)
        query = (
            session.query(DeviceReading)
            .filter(DeviceReading.device_id == device_id, DeviceReading.timestamp >= since)
            .order_by(desc(DeviceReading.timestamp))
            .limit(limit)
        )
        return pd.read_sql(query.statement, session.bind)
    finally:
        session.close()


# --- CONNECTION TEST -------------------------------------------------------

def test_device_connection(protocol: str, connection: dict, tag_map: list) -> dict:
    """Builds an adapter ad hoc (not tied to a saved Device row) and runs
    one connect+read+disconnect cycle. Used by the admin page's "Test
    Connection" button, both before a device is saved (to sanity-check
    connection details) and after (to sanity-check a tag map edit)."""
    from device_gateway.registry import build_adapter
    try:
        adapter = build_adapter(protocol, connection, tag_map)
        return adapter.test_connection()
    except Exception as exc:
        logger.exception(f"test_device_connection(protocol={protocol!r}) failed")
        return {"error": str(exc)}


def probe_tag_map(protocol: str, probe_tags: list) -> list:
    """Test Connection's throwaway tag map, built from the lines typed into
    the Probe Tags box.

    Modbus is the one protocol where the type decides what gets read: a
    "float" is two registers decoded as IEEE-754, so probing a plain counter
    that way came back as nonsense like 2.45e-41 and made a working PLC look
    broken. A Modbus probe now reads one raw register unless the line says
    otherwise ("40002:float", "40010:int32"). Every other protocol's raw_tag
    can legitimately contain a colon (OPC-UA node ids, MQTT "topic::path",
    regexes), so the suffix is only parsed for Modbus.
    """
    modbus = protocol in ("modbus_tcp", "modbus_rtu")
    rows = []
    for line in probe_tags or []:
        tag, data_type = str(line).strip(), "float"
        if not tag:
            continue
        if modbus:
            data_type = "int"
            head, sep, tail = tag.rpartition(":")
            if sep and tail.strip().lower() in ("int", "int16", "int32", "float"):
                tag, data_type = head.strip(), tail.strip().lower()
        rows.append({"raw_tag": tag, "canonical_metric": tag, "data_type": data_type, "scale_factor": 1.0})
    return rows


# --- GATEWAY PCs -------------------------------------------------------------
#
# A running gateway checks in every few seconds (service.py). These are what
# let the Device Registry say "no gateway is running" instead of repeating the
# last status a dead process happened to write.

GATEWAY_ONLINE_WITHIN_S = 45   # it checks in every 10 s; a slow database round can stretch that
GATEWAY_QUIET_S = 25           # two check-ins missed
DEVICE_STALE_MIN_S = 30
JOB_PICKUP_TIMEOUT_S = 60
JOB_RUN_TIMEOUT_S = 240


def record_gateway_heartbeat(hostname: str, ip_address: str, app_version: str, started_at: datetime) -> None:
    """Raises if the database can't be reached - the caller decides what an
    outage means, this just reports it."""
    session = ScopedSession()
    try:
        node = session.query(GatewayNode).filter(GatewayNode.hostname == hostname).first()
        if node is None:
            node = GatewayNode(hostname=hostname)
            session.add(node)
        node.ip_address = ip_address
        node.app_version = app_version
        node.started_at = started_at
        node.last_heartbeat_at = db_utc_now()
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_gateway_nodes() -> list:
    """Every gateway PC that has ever checked in, most recent first."""
    session = ScopedSession()
    try:
        rows = (session.query(GatewayNode, _seconds_since(GatewayNode.last_heartbeat_at))
                .order_by(desc(GatewayNode.last_heartbeat_at)).all())
        out = []
        for node, since in rows:
            since = float(since) if since is not None else None
            out.append({
                "hostname": node.hostname,
                "ip_address": node.ip_address,
                "app_version": node.app_version,
                "started_at": node.started_at,
                "last_heartbeat_at": node.last_heartbeat_at,
                "seconds_since_heartbeat": since,
                "online": since is not None and since <= GATEWAY_ONLINE_WITHIN_S,
            })
        return out
    finally:
        session.close()


def _ago(seconds: float | None) -> str:
    if seconds is None:
        return "ever"
    seconds = max(0, int(seconds))
    if seconds < 90:
        return f"{seconds} s"
    if seconds < 5400:
        return f"{seconds // 60} min"
    if seconds < 172800:
        return f"{seconds // 3600} h"
    return f"{seconds // 86400} days"


def effective_status(device: dict, gateways: list) -> tuple[str, str | None]:
    """What the Device Registry should show, as (status, explanation).

    The stored status is only ever as fresh as the last thing the gateway
    wrote. If the gateway stopped, it stopped writing, and a device that was
    Online stayed Online. This layers "Not reporting" on top whenever there
    is no evidence anything is still being read:

      * an Online device whose last reading is older than three polls (and
        at least DEVICE_STALE_MIN_S). Judged on the reading, not on gateway
        check-ins, so a gateway from before check-ins existed still shows
        Online for as long as it really is delivering.
      * a device that is No data / Unknown while no gateway is checking in -
        nothing is going to change that until one starts.
    """
    status = device.get("status") or "Unknown"
    error = device.get("last_error")
    if not device.get("is_enabled"):
        return status, error

    live = [g for g in gateways if g["online"]]
    if live:
        no_gateway = None
    elif gateways:
        newest = gateways[0]
        no_gateway = (f"No gateway PC has checked in for {_ago(newest['seconds_since_heartbeat'])} "
                      f"(last: {newest['hostname']}). Nothing is being read from this device - "
                      "start the gateway on that PC (START_HERE.bat, option 4).")
    else:
        no_gateway = ("No gateway PC has checked in yet. Nothing is being read from this device - "
                      "start the gateway on the PC cabled to it (START_HERE.bat, option 4). "
                      "A gateway on 4.06 or older doesn't check in; update that PC as well.")

    seen_s = device.get("seconds_since_seen")
    poll = float(device.get("poll_interval_s") or 5.0)
    stale = seen_s is None or seen_s > max(3 * poll, DEVICE_STALE_MIN_S)

    if status == "Online" and stale:
        if no_gateway:
            return "Not reporting", no_gateway
        beat_s = live[0]["seconds_since_heartbeat"] or 0
        if beat_s > GATEWAY_QUIET_S:
            # Still inside the "online" window, but it has already missed
            # check-ins: far more likely stopping (or lost the database) than
            # stuck on this one device.
            return "Not reporting", (f"No reading for {_ago(seen_s)}, and the gateway on {live[0]['hostname']} "
                                     f"hasn't checked in for {_ago(beat_s)} - it may have stopped or lost the database.")
        return "Not reporting", (f"No reading for {_ago(seen_s)}, although the gateway on "
                                 f"{live[0]['hostname']} is running - it may be stuck waiting on this device.")
    if status in ("No data", "Unknown") and no_gateway:
        return "Not reporting", no_gateway
    if status == "Error" and no_gateway and gateways:
        # The error is the last thing a gateway that has since stopped wrote;
        # the stopped gateway is the problem now. (With no check-in ever on
        # record the gateway may be an older one that doesn't check in, so an
        # Error is left alone rather than guessed at.)
        return "Not reporting", f"{no_gateway} Last error before it stopped: {error}" if error else no_gateway
    return status, error


# --- GATEWAY JOBS ------------------------------------------------------------

GATEWAY_JOB_KINDS = ("serial_ports", "subnet", "scan", "test_connection")


def create_gateway_job(target_host: str, kind: str, params: dict, created_by: str = "") -> int:
    if kind not in GATEWAY_JOB_KINDS:
        raise ValueError(f"Unknown gateway job {kind!r}")
    # test_connection can carry a broker/OPC-UA password; encrypt it with the
    # same key that protects saved devices.
    payload = encrypt_connection(params) if kind == "test_connection" else json.dumps(params or {})
    session = ScopedSession()
    try:
        job = GatewayJob(target_host=target_host, kind=kind, request_json=payload,
                         status="pending", created_by=created_by or None, created_at=db_utc_now())
        session.add(job)
        session.commit()
        return job.id
    finally:
        session.close()


def claim_next_gateway_job(hostname: str) -> dict | None:
    """Called by the gateway named `hostname`. Marks the oldest pending job
    for it as running and returns it, or None. SKIP LOCKED keeps two
    gateway processes on the same PC from both taking the same job. A job
    that has already waited past JOB_PICKUP_TIMEOUT_S is closed rather than
    run - the page asking for it has given up."""
    session = ScopedSession()
    try:
        row = (session.query(GatewayJob, _seconds_since(GatewayJob.created_at))
               .filter(GatewayJob.target_host == hostname, GatewayJob.status == "pending")
               .order_by(GatewayJob.id)
               .with_for_update(skip_locked=True, of=GatewayJob)
               .first())
        if row is None:
            session.commit()
            return None
        job, waited = row
        if waited is not None and float(waited) > JOB_PICKUP_TIMEOUT_S:
            job.status, job.error, job.request_json = "error", "Expired before this gateway picked it up.", None
            job.finished_at = db_utc_now()
            session.commit()
            return None
        job.status = "running"
        job.started_at = db_utc_now()
        session.commit()
        return {"id": job.id, "kind": job.kind, "request_json": job.request_json}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def decode_gateway_job_params(job: dict) -> dict:
    """Raises gateway_crypto.KeyMismatchError for a test_connection job this
    PC's key can't open."""
    if job["kind"] == "test_connection":
        return decrypt_connection_strict(job["request_json"] or "")
    return json.loads(job["request_json"] or "{}")


def finish_gateway_job(job_id: int, result=None, error: str | None = None) -> None:
    session = ScopedSession()
    try:
        job = session.get(GatewayJob, job_id)
        if job is None:
            return
        job.status = "error" if error else "done"
        job.error = error
        job.result_json = None if error else json.dumps(result, default=str)
        job.request_json = None  # no reason to keep a typed-in password around
        job.finished_at = db_utc_now()
        session.commit()
    finally:
        session.close()


def get_gateway_job(job_id: int) -> dict | None:
    """The job as the page sees it. A job nobody picked up, or one that has
    run far longer than any scan should, is closed here with a sentence the
    page can show, rather than left spinning forever."""
    session = ScopedSession()
    try:
        row = (session.query(GatewayJob, _seconds_since(GatewayJob.created_at),
                             _seconds_since(GatewayJob.started_at))
               .filter(GatewayJob.id == job_id).first())
        if row is None:
            return None
        job, waited, running = row
        if job.status == "pending" and waited is not None and float(waited) > JOB_PICKUP_TIMEOUT_S:
            job.status, job.request_json = "error", None
            job.error = (f"The gateway on {job.target_host} didn't pick this up within "
                         f"{JOB_PICKUP_TIMEOUT_S} s. Check that the gateway is running on that PC.")
            job.finished_at = db_utc_now()
            session.commit()
        elif job.status == "running" and running is not None and float(running) > JOB_RUN_TIMEOUT_S:
            job.status, job.request_json = "error", None
            job.error = f"The gateway on {job.target_host} started this but never finished it."
            job.finished_at = db_utc_now()
            session.commit()
        return {
            "id": job.id,
            "target_host": job.target_host,
            "kind": job.kind,
            "status": job.status,
            "result": json.loads(job.result_json) if job.result_json else None,
            "error": job.error,
        }
    finally:
        session.close()
