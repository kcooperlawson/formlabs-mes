"""
adapters/opcua_client.py - OPC-UA.

The modern standard for talking to PLCs/SCADA systems when Modbus isn't
available — increasingly common on newer Siemens/Beckhoff/Rockwell
(via UA gateway) equipment, and on anything that already calls itself
"Industry 4.0 ready." If the machine vendor mentions OPC-UA, an endpoint
URL, or a "server address" that looks like `opc.tcp://...`, this is the
adapter to use.

connection_json:
    {"endpoint": "opc.tcp://10.0.4.40:4840", "username": null, "password": null}

DeviceTagMap.raw_tag is a full OPC-UA node id, e.g.
    "ns=2;s=Machine1.Weight" or "ns=3;i=1002"
(get these from the vendor's tag list, or by browsing the server's address
space with a generic OPC-UA client like UaExpert before wiring up the tag
map here).

Requires: opcua (the "python-opcua" package — simpler, synchronous API;
swap to asyncua later if you need subscriptions instead of polling).
"""
from .base import DeviceAdapter


class OPCUAAdapter(DeviceAdapter):
    def __init__(self, connection: dict, tag_map: list):
        super().__init__(connection, tag_map)
        self.client = None

    def connect(self) -> None:
        from opcua import Client
        self.client = Client(self.connection["endpoint"])
        if self.connection.get("username"):
            self.client.set_user(self.connection["username"])
            self.client.set_password(self.connection.get("password", ""))
        self.client.connect()

    def _read_raw(self) -> dict:
        raw = {}
        for entry in self.tag_map:
            node_id = entry.get("raw_tag")
            try:
                node = self.client.get_node(node_id)
                raw[node_id] = node.get_value()
            except Exception:
                continue
        return raw

    def close(self) -> None:
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
