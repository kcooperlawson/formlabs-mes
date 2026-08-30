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
from sqlalchemy import desc

from db_core import ScopedSession
from models import PumpStation, Reactor
from device_models import Device, DeviceTagMap, DeviceReading
from app_logger import logger


# --- DEVICES ---------------------------------------------------------------

def get_devices_df() -> pd.DataFrame:
    """One row per device, with the pump station / reactor it's assigned
    to resolved to a readable name (not just the FK id) for display on the
    admin page."""
    session = ScopedSession()
    try:
        rows = (
            session.query(Device, PumpStation.station_name, Reactor.reactor_name)
            .outerjoin(PumpStation, Device.pump_station_id == PumpStation.id)
            .outerjoin(Reactor, Device.reactor_id == Reactor.id)
            .order_by(Device.device_name)
            .all()
        )
        records = []
        for device, pump_name, reactor_name in rows:
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
            "connection": json.loads(device.connection_json or "{}"),
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


def create_device(device_name: str, device_role: str, protocol: str, connection: dict,
                   poll_interval_s: float = 5.0, pump_station_id: int | None = None,
                   reactor_id: int | None = None, notes: str = "", is_enabled: bool = True) -> int | None:
    session = ScopedSession()
    try:
        if session.query(Device).filter(Device.device_name == device_name.strip()).first():
            return None
        device = Device(
            device_name=device_name.strip(), device_role=device_role, protocol=protocol,
            connection_json=json.dumps(connection), poll_interval_s=poll_interval_s,
            pump_station_id=pump_station_id, reactor_id=reactor_id, notes=notes,
            is_enabled=is_enabled, status="Unknown",
        )
        session.add(device)
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
            fields["connection_json"] = json.dumps(fields.pop("connection"))
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
