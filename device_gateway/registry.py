"""
device_gateway/registry.py - Protocol name -> adapter class.

This is the ONE place that has to change when a new protocol shows up.
Everything else (the gateway service, the admin page's Test Connection
button, writer.py) works against the DeviceAdapter interface and never
needs to know the list grew.

To add protocol X:
  1. Write device_gateway/adapters/x.py implementing DeviceAdapter
     (connect / _read_raw / close — see adapters/base.py).
  2. Import it below and add one line to ADAPTERS.
That's the whole integration.
"""
import json

from .adapters.modbus_tcp import ModbusTCPAdapter
from .adapters.modbus_rtu import ModbusRTUAdapter
from .adapters.opcua_client import OPCUAAdapter
from .adapters.mqtt_client import MQTTAdapter
from .adapters.serial_ascii import SerialASCIIAdapter
from .adapters.http_poll import HTTPPollAdapter

ADAPTERS = {
    "modbus_tcp": ModbusTCPAdapter,
    "modbus_rtu": ModbusRTUAdapter,
    "opcua": OPCUAAdapter,
    "mqtt": MQTTAdapter,
    "serial_ascii": SerialASCIIAdapter,
    "http_poll": HTTPPollAdapter,
}

# Shown in the admin page's protocol dropdown, in this order.
PROTOCOL_LABELS = {
    "modbus_tcp": "Modbus TCP/IP (most PLC & HMI panels)",
    "modbus_rtu": "Modbus RTU (RS-485/RS-232 serial)",
    "opcua": "OPC-UA",
    "mqtt": "MQTT",
    "serial_ascii": "Serial ASCII (bench scales, simple text streams)",
    "http_poll": "HTTP / REST (JSON status endpoint)",
}


def build_adapter(protocol: str, connection: dict, tag_map: list):
    """tag_map here is a list of plain dicts, e.g.
    [{"raw_tag": "...", "canonical_metric": "...", "data_type": "float",
      "scale_factor": 1.0}, ...] — see device_crud.get_tag_map_dicts()."""
    cls = ADAPTERS.get(protocol)
    if cls is None:
        raise ValueError(
            f"No adapter registered for protocol {protocol!r}. "
            f"Known protocols: {sorted(ADAPTERS)}. "
            f"Add one in device_gateway/adapters/ and register it in "
            f"device_gateway/registry.py."
        )
    return cls(connection, tag_map)


def build_adapter_from_device(device, tag_map_rows) -> "DeviceAdapter":
    """Convenience wrapper that takes ORM rows directly (a Device row and
    its DeviceTagMap rows) instead of already-unpacked dicts."""
    connection = json.loads(device.connection_json or "{}")
    tag_map = [
        {
            "raw_tag": t.raw_tag,
            "canonical_metric": t.canonical_metric,
            "data_type": t.data_type or "float",
            "scale_factor": t.scale_factor if t.scale_factor is not None else 1.0,
        }
        for t in tag_map_rows
    ]
    return build_adapter(device.protocol, connection, tag_map)
