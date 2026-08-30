"""
adapters/http_poll.py - Plain HTTP/REST polling.

For newer controllers that expose a local web API or a status JSON
endpoint (some label printers do this — check for a built-in web UI and
poke around its Network tab for an XHR request that returns JSON) instead
of a fieldbus protocol. Also the easiest fallback for a one-off custom
integration: point this at anything that returns JSON and it works.

connection_json:
    {"url": "http://10.0.4.60/api/status", "method": "GET",
     "headers": {"Authorization": "Bearer ..."}, "timeout_s": 5}

DeviceTagMap.raw_tag is a dotted JSON path into the response body, e.g.
    "data.weight_g"  or  "printer.counters.printed"

Requires: requests (see requirements-device-gateway.txt)
"""
from .base import DeviceAdapter


def _get_path(obj, path: str):
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        elif isinstance(obj, list) and part.isdigit():
            idx = int(part)
            obj = obj[idx] if 0 <= idx < len(obj) else None
        else:
            return None
    return obj


class HTTPPollAdapter(DeviceAdapter):
    def __init__(self, connection: dict, tag_map: list):
        super().__init__(connection, tag_map)
        self.session = None

    def connect(self) -> None:
        import requests
        self.session = requests.Session()
        # Fail fast on a genuinely unreachable host rather than waiting
        # until the first real poll.
        self._read_raw()

    def _read_raw(self) -> dict:
        import requests
        url = self.connection["url"]
        method = self.connection.get("method", "GET").upper()
        headers = self.connection.get("headers") or {}
        timeout = float(self.connection.get("timeout_s", 5))
        session = self.session or requests
        response = session.request(method, url, headers=headers, timeout=timeout)
        response.raise_for_status()
        body = response.json()
        raw = {}
        for entry in self.tag_map:
            path = entry.get("raw_tag")
            value = _get_path(body, path)
            if value is not None:
                raw[path] = value
        return raw

    def close(self) -> None:
        if self.session:
            self.session.close()
