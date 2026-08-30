"""
adapters/modbus_tcp.py - Modbus TCP/IP.

This is the single most likely protocol for the pump/filling controllers
in the photos: that touchscreen HMI panel (POURING / MATERIALS / MANUAL /
SETTINGS tabs) is very typical of an industrial PLC-driven dispensing
skid, and the overwhelming majority of PLCs and HMI panels from this era
(AutomationDirect, Red Lion, Allen-Bradley via a gateway, Siemens via a
gateway, etc.) expose their live tags over Modbus TCP even when the
touchscreen itself doesn't advertise it — it's usually one setting to turn
on in the PLC's project. Worth asking whoever built/maintains it "does it
have a Modbus TCP server?" before assuming you need something more exotic.

connection_json:
    {"host": "10.0.4.22", "port": 502, "unit_id": 1}

DeviceTagMap.raw_tag for this adapter is a Modbus register address as a
plain integer string, e.g. "3000" or "40001" (either 0-based or the
traditional 40001-style Modicon addressing both work — see _resolve_address).
data_type controls how many registers get read and how they're decoded:
    "int16"  - 1 register, unsigned 16-bit
    "int32"  - 2 registers, unsigned 32-bit, big-endian word order
    "float"  - 2 registers, IEEE-754 float32, big-endian word order
    (anything else defaults to "int16")

Byte/word order varies by PLC vendor. This adapter assumes big-endian
words (the common case); if a mapped value looks scrambled or off by a
huge factor, that's almost always a word-order or address-offset mismatch
— fix it here in _decode_registers() rather than in the tag map.

Requires: pymodbus>=3.0 (see requirements-device-gateway.txt)
"""
import struct
from .base import DeviceAdapter


def _resolve_address(raw_tag: str) -> int:
    n = int(raw_tag)
    # Traditional Modicon-style addressing (40001, 30001, ...) encodes the
    # register *type* in the leading digit; strip it down to a 0-based
    # offset within the holding-register space this adapter reads from.
    if n >= 40001:
        return n - 40001
    if n >= 30001:
        return n - 30001
    return n


class ModbusTCPAdapter(DeviceAdapter):
    def __init__(self, connection: dict, tag_map: list):
        super().__init__(connection, tag_map)
        self.client = None
        self.unit_id = int(connection.get("unit_id", 1))

    def connect(self) -> None:
        from pymodbus.client import ModbusTcpClient
        self.client = ModbusTcpClient(
            host=self.connection["host"],
            port=int(self.connection.get("port", 502)),
            timeout=float(self.connection.get("timeout_s", 3)),
        )
        if not self.client.connect():
            raise ConnectionError(
                f"Modbus TCP: could not reach {self.connection.get('host')}:"
                f"{self.connection.get('port', 502)}")

    def _read_raw(self) -> dict:
        raw = {}
        for entry in self.tag_map:
            raw_tag = entry.get("raw_tag")
            data_type = entry.get("data_type", "int16")
            count = 2 if data_type in ("int32", "float") else 1
            try:
                address = _resolve_address(raw_tag)
                result = self.client.read_holding_registers(
                    address=address, count=count, slave=self.unit_id)
                if result is None or result.isError():
                    continue
                raw[raw_tag] = self._decode_registers(result.registers, data_type)
            except Exception:
                # One bad/unreachable register shouldn't blank out every
                # other tag on this device this cycle.
                continue
        return raw

    @staticmethod
    def _decode_registers(registers: list, data_type: str):
        if data_type == "int32":
            packed = struct.pack(">HH", registers[0], registers[1])
            return struct.unpack(">I", packed)[0]
        if data_type == "float":
            packed = struct.pack(">HH", registers[0], registers[1])
            return struct.unpack(">f", packed)[0]
        return registers[0]

    def close(self) -> None:
        if self.client:
            self.client.close()
