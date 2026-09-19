"""
adapters/mqtt_client.py - MQTT.

The right fit for anything IIoT-ish: a machine (or a Raspberry Pi/gateway
bolted onto an older machine) that publishes readings to a broker rather
than waiting to be polled. Increasingly common for label printers and
newer scales/PLCs that ship with "connect it to the cloud" in mind. If
someone says the machine "publishes to MQTT" or mentions a topic name,
this is the adapter.

connection_json:
    {"host": "10.0.4.5", "port": 1883, "username": null, "password": null,
     "client_id": "formlabs-gateway"}

DeviceTagMap.raw_tag is the MQTT topic to subscribe to, e.g.
    "plant/pump3/weight"
The adapter subscribes to every tag's topic on connect and keeps the most
recent payload for each. Payloads are parsed as JSON when possible (in
which case, use "topic::json.key.path" as raw_tag to pull one field out of
a JSON payload, e.g. "plant/pump3/status::state"); otherwise the raw
payload text is used as-is.

Requires: paho-mqtt (see requirements-device-gateway.txt)
"""
import json
import threading
import time
from .base import DeviceAdapter

# Long enough for paho's own reconnect after a broker restart, short enough
# that a broker that has really gone shows up on the admin page within a poll
# or two.
DISCONNECTED_GRACE_S = 15.0


def _get_json_path(obj, path: str):
    for part in path.split("."):
        if isinstance(obj, dict):
            obj = obj.get(part)
        else:
            return None
    return obj


class MQTTAdapter(DeviceAdapter):
    def __init__(self, connection: dict, tag_map: list):
        super().__init__(connection, tag_map)
        self.client = None
        self._latest: dict = {}
        self._lock = threading.Lock()
        # topic -> list of (raw_tag, json_path_or_None) so one topic can
        # feed multiple canonical metrics.
        self._topics: dict = {}
        # Connection state from paho's own callbacks. paho reconnects by
        # itself in the background, but until now nothing noticed while it
        # couldn't: the last payload per topic kept being returned, so a
        # dead broker looked like a machine whose values never change.
        self._connected = False
        self._disconnected_since = None
        self._refused_rc = None
        for entry in self.tag_map:
            raw_tag = entry.get("raw_tag", "")
            topic, _, json_path = raw_tag.partition("::")
            self._topics.setdefault(topic, []).append((raw_tag, json_path or None))

    def connect(self) -> None:
        import paho.mqtt.client as mqtt
        self.client = mqtt.Client(client_id=self.connection.get("client_id", "formlabs-gateway"))
        if self.connection.get("username"):
            self.client.username_pw_set(self.connection["username"], self.connection.get("password", ""))
        self.client.on_message = self._on_message
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self._disconnected_since = time.monotonic()
        self.client.connect(self.connection["host"], int(self.connection.get("port", 1883)), keepalive=30)
        self.client.loop_start()
        for topic in self._topics:
            self.client.subscribe(topic)

    def _on_connect(self, client, _userdata, _flags, rc):
        if rc == 0:
            self._connected, self._disconnected_since, self._refused_rc = True, None, None
            # Subscriptions don't survive a reconnect with a clean session.
            for topic in self._topics:
                client.subscribe(topic)
        else:
            self._connected, self._refused_rc = False, rc

    def _on_disconnect(self, _client, _userdata, _rc):
        if self._connected or self._disconnected_since is None:
            self._disconnected_since = time.monotonic()
        self._connected = False

    def _on_message(self, _client, _userdata, msg):
        payload = msg.payload.decode(errors="ignore")
        try:
            parsed = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        with self._lock:
            for raw_tag, json_path in self._topics.get(msg.topic, []):
                if json_path and isinstance(parsed, dict):
                    self._latest[raw_tag] = _get_json_path(parsed, json_path)
                else:
                    self._latest[raw_tag] = parsed if parsed is not None else payload

    def _read_raw(self) -> dict:
        where = f"{self.connection.get('host')}:{self.connection.get('port', 1883)}"
        if self._refused_rc:
            raise ConnectionError(f"MQTT: broker at {where} refused the connection (rc={self._refused_rc}) - check the username and password")
        if not self._connected and self._disconnected_since is not None                 and time.monotonic() - self._disconnected_since > DISCONNECTED_GRACE_S:
            raise ConnectionError(f"MQTT: not connected to the broker at {where} for "
                                  f"{time.monotonic() - self._disconnected_since:.0f} s")
        with self._lock:
            return dict(self._latest)

    def close(self) -> None:
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
