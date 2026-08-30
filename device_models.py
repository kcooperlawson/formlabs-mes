"""
device_models.py - Schema for the protocol-agnostic Device Gateway.

Additive only: nothing here touches an existing table, column, or import in
models.py. It gives every floor machine (pump/filling controller, bench
scale, label printer, whatever gets wired in next) one row in `devices`,
regardless of what protocol it happens to speak — the protocol lives in a
column, not in the table you have to pick.

Wire this in by adding two lines to database.py's facade imports:

    from device_models import Device, DeviceTagMap, DeviceReading
    from device_crud import *

See README_DEVICE_GATEWAY.md for the full integration walkthrough.
"""
from sqlalchemy import Column, Integer, String, Float, DateTime, Text, ForeignKey, Boolean
from datetime import datetime
from db_core import Base


class Device(Base):
    """One physical machine on the floor.

    Protocol-specific connection details (IP/port, COM port/baud, broker
    URL, OPC-UA endpoint, HTTP base URL — whatever that protocol needs)
    live in `connection_json` as a small JSON blob instead of one column
    per protocol, so adding a new protocol never means a migration for
    this table. See device_gateway/adapters/*.py for what each protocol
    expects inside connection_json.
    """
    __tablename__ = "devices"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_name = Column(String(100), unique=True, nullable=False)

    # filling_station | scale | label_printer | reactor_sensor | other
    device_role = Column(String(30), nullable=False, default="filling_station")

    # modbus_tcp | modbus_rtu | opcua | mqtt | serial_ascii | http_poll
    protocol = Column(String(30), nullable=False)
    connection_json = Column(Text, nullable=False, default="{}")
    poll_interval_s = Column(Float, default=5.0)
    is_enabled = Column(Boolean, default=True, nullable=False)

    # "Assign" = point this device at the existing pump station / reactor it
    # physically sits on. This is the whole reason readings land in
    # Analytics automatically: pump_station_id is the same FK ProductionLog
    # and AssignedRun already key off of.
    pump_station_id = Column(Integer, ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True, index=True)
    reactor_id = Column(Integer, ForeignKey("reactors.id", ondelete="SET NULL"), nullable=True, index=True)

    status = Column(String(20), default="Unknown")  # Online | Offline | Error | Unknown
    last_seen_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class DeviceTagMap(Base):
    """One row = one raw tag on a device, mapped to one canonical metric
    (see device_gateway/normalize.py: CANONICAL_METRICS) the rest of the
    system understands. This is what a person fills in after hitting "Test
    Connection" on the admin page and seeing what the machine actually
    reports back.

    `raw_tag` means something different per protocol — a Modbus register
    address, an OPC-UA node id, an MQTT topic, a JSON path for http_poll,
    or a named regex group for serial_ascii — the adapter for that
    protocol is what interprets it.
    """
    __tablename__ = "device_tag_maps"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    raw_tag = Column(String(255), nullable=False)
    canonical_metric = Column(String(50), nullable=False)
    data_type = Column(String(20), default="float")  # float | int | string | bool
    scale_factor = Column(Float, default=1.0)
    unit = Column(String(20), nullable=True)


class DeviceReading(Base):
    """Append-only raw audit trail: every normalized reading the gateway
    pulled, before any business-rule interpretation (see writer.py).
    Analytics can query this directly for machine-level telemetry — fault
    codes, uptime, raw weight curves — even for metrics that never get
    promoted into a ProductionLog row.
    """
    __tablename__ = "device_readings"
    id = Column(Integer, primary_key=True, autoincrement=True)
    device_id = Column(Integer, ForeignKey("devices.id", ondelete="CASCADE"), nullable=False, index=True)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    metric = Column(String(50), nullable=False, index=True)
    value_numeric = Column(Float, nullable=True)
    value_text = Column(String(255), nullable=True)
