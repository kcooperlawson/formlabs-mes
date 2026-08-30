"""
adapters/base.py - The one contract every protocol adapter has to honor.

The gateway service (device_gateway/service.py) and the admin page's "Test
Connection" button only ever talk to this interface. Neither knows or cares
whether a given device is Modbus, OPC-UA, MQTT, a scale's raw serial
stream, or something not written yet. That's the whole point: to support a
new protocol, write one new file in this folder that implements
DeviceAdapter, add one line to registry.py, and nothing else in the system
changes.

Each adapter is constructed with:
  connection: dict   - protocol-specific connection info, parsed from
                        Device.connection_json (host/port, COM port/baud,
                        broker URL, endpoint URL, ...)
  tag_map:   list[dict] - the device's DeviceTagMap rows, as plain dicts:
                        {"raw_tag": ..., "canonical_metric": ...,
                         "data_type": "float"|"int"|"string"|"bool",
                         "scale_factor": 1.0}

poll() always returns canonical metric names as keys (already mapped,
scaled, and type-cast) — never raw tag names. That's what lets writer.py
and the admin UI work the same way regardless of protocol.
"""
from abc import ABC, abstractmethod
from typing import Any


class DeviceAdapter(ABC):
    def __init__(self, connection: dict, tag_map: list):
        self.connection = connection or {}
        self.tag_map = tag_map or []

    @abstractmethod
    def connect(self) -> None:
        """Open whatever connection this protocol needs. Raise on failure —
        the gateway service catches it, marks the device Offline/Error with
        the exception text, and retries on its normal backoff."""
        ...

    @abstractmethod
    def _read_raw(self) -> dict:
        """Protocol-specific: return {raw_tag: raw_value} for every tag in
        self.tag_map that could be read this cycle. A tag that couldn't be
        read (register timeout, topic hasn't published yet) is simply
        omitted rather than raising, so one bad tag doesn't blank out a
        device's whole reading."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Release the connection. Must be safe to call even if connect()
        never succeeded."""
        ...

    def poll(self) -> dict:
        """Read once and return {canonical_metric: cast_and_scaled_value}.
        Adapters should not override this — override _read_raw() instead."""
        raw = self._read_raw()
        return self._apply_tag_map(raw)

    def test_connection(self) -> dict:
        """Used by the admin page's 'Test Connection' button: connect, read
        once, disconnect, return {"raw": {...}, "mapped": {...}} so a
        person can see exactly what the machine reports before (or after)
        writing tag map rows for it."""
        self.connect()
        try:
            raw = self._read_raw()
            return {"raw": raw, "mapped": self._apply_tag_map(raw)}
        finally:
            self.close()

    def _apply_tag_map(self, raw: dict) -> dict:
        mapped: dict[str, Any] = {}
        for entry in self.tag_map:
            raw_tag = entry.get("raw_tag")
            if raw_tag not in raw:
                continue
            value = raw[raw_tag]
            value = self._cast(value, entry.get("data_type", "float"))
            # bool is a subclass of int in Python, so this check has to
            # exclude it explicitly — otherwise a scale_factor multiply
            # below silently turns True/False into 1.0/0.0.
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                value = value * float(entry.get("scale_factor", 1.0) or 1.0)
            mapped[entry["canonical_metric"]] = value
        return mapped

    @staticmethod
    def _cast(value: Any, data_type: str) -> Any:
        try:
            if data_type == "float":
                return float(value)
            if data_type == "int":
                return int(float(value))
            if data_type == "bool":
                if isinstance(value, str):
                    return value.strip().lower() in ("1", "true", "on", "yes")
                return bool(value)
            return str(value)
        except (TypeError, ValueError):
            return value
