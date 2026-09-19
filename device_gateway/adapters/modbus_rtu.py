"""
adapters/modbus_rtu.py - Modbus over RS-485/RS-232 serial.

Same register model as modbus_tcp.py (see that file for raw_tag/data_type
conventions) — the only difference is the transport. Use this for older
PLCs/HMIs that only expose a serial port (RS-485 terminal block, or a
USB-to-RS485 dongle at the panel) instead of Ethernet.

connection_json:
    {"port": "COM5", "baud": 9600, "parity": "N", "stopbits": 1,
     "bytesize": 8, "unit_id": 1}

("port" is "/dev/ttyUSB0" on Linux, "COM5" on Windows — whatever the OS
running the gateway process sees the adapter as.)

Requires: pymodbus>=3.0, pyserial (see requirements-device-gateway.txt)
"""
from .modbus_tcp import _resolve_address, raise_all_registers_failed
from .base import DeviceAdapter
import struct


class ModbusRTUAdapter(DeviceAdapter):
    def __init__(self, connection: dict, tag_map: list):
        super().__init__(connection, tag_map)
        self.client = None
        self.unit_id = int(connection.get("unit_id", 1))

    def connect(self) -> None:
        from pymodbus.client import ModbusSerialClient
        self.client = ModbusSerialClient(
            port=self.connection["port"],
            baudrate=int(self.connection.get("baud", 9600)),
            parity=self.connection.get("parity", "N"),
            stopbits=int(self.connection.get("stopbits", 1)),
            bytesize=int(self.connection.get("bytesize", 8)),
            timeout=float(self.connection.get("timeout_s", 3)),
        )
        if not self.client.connect():
            raise ConnectionError(f"Modbus RTU: could not open {self.connection.get('port')}")

    def _read_raw(self) -> dict:
        raw = {}
        failure = None
        bad_addresses = []
        for entry in self.tag_map:
            raw_tag = entry.get("raw_tag")
            data_type = entry.get("data_type", "int16")
            count = 2 if data_type in ("int32", "float") else 1
            try:
                address = _resolve_address(raw_tag)
            except ValueError:
                bad_addresses.append(raw_tag)
                continue
            try:
                result = self.client.read_holding_registers(
                    address=address, count=count, slave=self.unit_id)
                if result is None or result.isError():
                    continue
                raw[raw_tag] = self._decode_registers(result.registers, data_type)
            except Exception as exc:
                failure = exc
                continue
        if self.tag_map and not raw:
            raise_all_registers_failed("Modbus RTU", str(self.connection.get("port")), len(self.tag_map), failure, bad_addresses)
        return raw

    @staticmethod
    def _decode_registers(registers: list, data_type: str):
        if data_type == "int32":
            return struct.unpack(">I", struct.pack(">HH", registers[0], registers[1]))[0]
        if data_type == "float":
            return struct.unpack(">f", struct.pack(">HH", registers[0], registers[1]))[0]
        return registers[0]

    def close(self) -> None:
        if self.client:
            self.client.close()
