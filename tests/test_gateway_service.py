"""Device Gateway service: what a device worker does when the machine goes
quiet, when the machine errors, and when the DATABASE goes away - plus the
adapter-level checks that feed it.

Before 4.07 a database error anywhere in the gateway's rescan loop ended the
process for good, a PLC that dropped off the network after connecting stayed
"Online" (an empty poll wasn't an error), and a gateway PC whose encryption
key didn't match failed every device with KeyError: 'host'. Each of those is
pinned down here with fake adapters, so it runs in seconds. The end-to-end
version, with a real gateway process, real sockets and cables that get
pulled, is dev/simulate_gateway_network.py.
"""
import os
import pathlib
import socket
import struct
import sys
import threading
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402

boot(fresh=True)

import crud  # noqa: E402

crud.init_db()

from sqlalchemy.exc import OperationalError  # noqa: E402

import device_crud  # noqa: E402
from db_core import ScopedSession  # noqa: E402
from device_gateway import service  # noqa: E402
from device_models import Device, GatewayNode  # noqa: E402

FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(label)
        print(f"  FAIL  {label}")


def wait_for(pred, timeout=10.0):
    started = time.time()
    while time.time() - started < timeout:
        if pred():
            return True
        time.sleep(0.1)
    return False


def device_row(device_id):
    session = ScopedSession()
    try:
        d = session.get(Device, device_id)
        return {"status": d.status, "last_error": d.last_error, "last_seen_at": d.last_seen_at}
    finally:
        session.close()


print("=" * 66)
print("GATEWAY SERVICE: outages, silent devices, honest status")
print("=" * 66)

# Fast clocks for a test run.
service.DB_RETRY_S = 0.3
service.MAX_BACKOFF_S = 0.5
service.RESCAN_INTERVAL_S = 0.5


class FakeAdapter:
    """Whatever the test sets on the class is what the 'machine' does."""
    polls = []          # callables, used in order; the last one repeats
    connects = 0

    def __init__(self, *_):
        pass

    def connect(self):
        FakeAdapter.connects += 1

    def poll(self):
        step = FakeAdapter.polls[0] if len(FakeAdapter.polls) == 1 else FakeAdapter.polls.pop(0)
        return step()

    def close(self):
        pass


real_builder = service.build_adapter_from_device
service.build_adapter_from_device = lambda device, tags: FakeAdapter()

device_id = device_crud.create_device("Worker Test PLC", "scale", "modbus_tcp",
                                      {"host": "10.0.0.1", "port": 502}, poll_interval_s=0.2)
device_crud.upsert_tag_map_row(device_id, "40001", "weight_g", "int")
writer = service.ReadingWriter()

# --- connected, but nothing comes back ----------------------------------------
FakeAdapter.polls = [lambda: {}]
worker = service.DeviceWorker(device_id, writer)
worker.start()
check(wait_for(lambda: device_row(device_id)["status"] == "No data"),
      f"a device that connects but returns nothing is No data, not Online (got {device_row(device_id)})")
row = device_row(device_id)
check("none of its 1 mapped tag" in (row["last_error"] or ""), f"...and says so (got {row['last_error']!r})")
check(row["last_seen_at"] is None, f"...and 'last seen' is not refreshed by an empty poll (got {row['last_seen_at']})")

# --- data arrives ----------------------------------------------------------------
FakeAdapter.polls = [lambda: {"weight_g": 850.0}]
check(wait_for(lambda: device_row(device_id)["status"] == "Online"), f"real data makes it Online (got {device_row(device_id)})")
row = device_row(device_id)
check(row["last_seen_at"] is not None and row["last_error"] is None, f"...with last seen set and no error (got {row})")

# --- the machine errors -------------------------------------------------------------
def unreachable():
    raise ConnectionError("Modbus TCP: no response from 10.0.0.1:502")


FakeAdapter.polls = [unreachable]
check(wait_for(lambda: device_row(device_id)["status"] == "Error"), f"an adapter error shows as Error (got {device_row(device_id)})")
check("no response" in (device_row(device_id)["last_error"] or ""), "...with the adapter's own message")
check(worker.is_alive(), "the worker keeps running after a device error")
connects_before = FakeAdapter.connects
FakeAdapter.polls = [lambda: {"weight_g": 851.0}]
check(wait_for(lambda: device_row(device_id)["status"] == "Online"), "it reconnects and recovers by itself")
check(FakeAdapter.connects > connects_before, "...by reconnecting, not by reusing the broken session")

# --- the DATABASE goes away -------------------------------------------------------
real_load = service.DeviceWorker._load
outage = {"on": True}


def flaky_load(self):
    if outage["on"]:
        raise OperationalError("SELECT devices", {}, Exception("connection refused"))
    return real_load(self)


service.DeviceWorker._load = flaky_load
time.sleep(1.5)
check(worker.is_alive(), "a database outage doesn't kill the device worker")
outage["on"] = False
session = ScopedSession()
session.query(Device).filter(Device.id == device_id).update({"status": "Unknown"})
session.commit()
session.close()
check(wait_for(lambda: device_row(device_id)["status"] == "Online"), f"...and it picks up again when the database is back (got {device_row(device_id)})")
service.DeviceWorker._load = real_load

# --- silent for too long: reconnect -----------------------------------------------
service.NO_DATA_RECONNECT_S = 0.5
connects_before = FakeAdapter.connects
FakeAdapter.polls = [lambda: {}]
check(wait_for(lambda: FakeAdapter.connects > connects_before + 1, 6), "a device silent past NO_DATA_RECONNECT_S gets reconnected")
check(worker.is_alive(), "...without the worker dying")

# --- disabled: the worker leaves -----------------------------------------------------
device_crud.set_device_enabled(device_id, False)
# is_alive() on a FINISHED worker is the call that used to raise "'Event' object
# is not callable": the worker kept its stop flag in self._stop, which is the
# name threading.Thread uses internally. The rescan loop makes exactly this
# call, so one finished worker broke every rescan after it.
check(wait_for(lambda: not worker.is_alive(), 6), "disabling the device stops its worker, and a finished worker can be asked if it's alive")

# --- run_forever: the loop that used to die on the first database error ------------
real_heartbeat = device_crud.record_gateway_heartbeat
beat_outage = {"on": True}


def flaky_heartbeat(*args, **kwargs):
    if beat_outage["on"]:
        raise OperationalError("INSERT gateway_nodes", {}, Exception("server closed the connection unexpectedly"))
    return real_heartbeat(*args, **kwargs)


device_crud.record_gateway_heartbeat = flaky_heartbeat
loop = threading.Thread(target=service.run_forever, daemon=True, name="run-forever-under-test")
loop.start()
time.sleep(2)
check(loop.is_alive(), "run_forever survives database errors in its own loop (this is what used to end the process)")
beat_outage["on"] = False


def checked_in():
    session = ScopedSession()
    try:
        return session.query(GatewayNode).filter(GatewayNode.hostname == socket.gethostname()).first() is not None
    finally:
        session.close()


check(wait_for(checked_in, 6), "...and checks in once the database answers again")
device_crud.record_gateway_heartbeat = real_heartbeat

FakeAdapter.polls = [lambda: {"weight_g": 852.0}]
session = ScopedSession()
session.query(Device).filter(Device.id == device_id).update({"status": "Unknown"})
session.commit()
session.close()
device_crud.set_device_enabled(device_id, True)
check(wait_for(lambda: device_row(device_id)["status"] == "Online", 8),
      f"the running gateway starts a worker for a device enabled while it runs (got {device_row(device_id)})")
device_crud.set_device_enabled(device_id, False)
time.sleep(1.5)
device_crud.set_device_enabled(device_id, True)
session = ScopedSession()
session.query(Device).filter(Device.id == device_id).update({"status": "Unknown"})
session.commit()
session.close()
check(wait_for(lambda: device_row(device_id)["status"] == "Online", 8),
      f"...and again after it was switched off and back on (got {device_row(device_id)})")
device_crud.set_device_enabled(device_id, False)
time.sleep(1)
service.build_adapter_from_device = real_builder

# --- the encryption key --------------------------------------------------------------
from cryptography.fernet import Fernet  # noqa: E402

from device_gateway.registry import build_adapter_from_device  # noqa: E402
from device_models import DeviceTagMap  # noqa: E402
from gateway_crypto import KeyMismatchError  # noqa: E402

session = ScopedSession()
saved = session.get(Device, device_id)
tag_rows = session.query(DeviceTagMap).filter(DeviceTagMap.device_id == device_id).all()
_ = (saved.connection_json, saved.protocol)
for t in tag_rows:
    _ = (t.raw_tag, t.canonical_metric, t.data_type, t.scale_factor)
session.close()

import gateway_crypto  # noqa: E402


def refuse_to_write_env(*_):
    raise AssertionError("the key test must never write to .env")


gateway_crypto._append_to_env = refuse_to_write_env
real_key = os.environ.get("GATEWAY_ENCRYPTION_KEY")
for label, value in (("a different", Fernet.generate_key().decode()), ("no", "")):
    os.environ["GATEWAY_ENCRYPTION_KEY"] = value
    try:
        build_adapter_from_device(saved, tag_rows)
        message = None
    except KeyMismatchError as exc:
        message = str(exc)
    except Exception as exc:
        message = f"wrong exception: {type(exc).__name__}: {exc}"
    check(message is not None and "Copy the GATEWAY_ENCRYPTION_KEY line" in message,
          f"a gateway PC with {label} key gets told what to copy, not KeyError: 'host' (got {message!r})")
os.environ["GATEWAY_ENCRYPTION_KEY"] = real_key
check(build_adapter_from_device(saved, tag_rows).connection.get("host") == "10.0.0.1", "the right key still opens it")

# --- adapters: every register failing is an error, not an empty reading ------------
from device_gateway.adapters.modbus_tcp import ModbusTCPAdapter  # noqa: E402


def refusing_plc(listener):
    """Answers every read with Modbus exception 2, illegal data address."""
    while True:
        try:
            conn, _ = listener.accept()
        except OSError:
            return
        try:
            while True:
                header = conn.recv(7)
                if len(header) < 7:
                    break
                tid, _pid, length, unit = struct.unpack(">HHHB", header)
                pdu = conn.recv(length - 1)
                conn.sendall(struct.pack(">HHHB", tid, 0, 3, unit) + bytes([pdu[0] | 0x80, 2]))
        except OSError:
            pass
        finally:
            conn.close()


listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(4)
port = listener.getsockname()[1]
threading.Thread(target=refusing_plc, args=(listener,), daemon=True).start()

adapter = ModbusTCPAdapter({"host": "127.0.0.1", "port": port, "unit_id": 1, "timeout_s": 2},
                           [{"raw_tag": "40001", "canonical_metric": "weight_g", "data_type": "int", "scale_factor": 1.0}])
adapter.connect()
try:
    adapter.poll()
    message = None
except ConnectionError as exc:
    message = str(exc)
adapter.close()
check(message is not None and "refused all 1 mapped register" in message,
      f"a PLC refusing every register raises, pointing at the addresses (got {message!r})")

adapter = ModbusTCPAdapter({"host": "127.0.0.1", "port": port, "unit_id": 1, "timeout_s": 2},
                           [{"raw_tag": "4000140002", "canonical_metric": "weight_g", "data_type": "int", "scale_factor": 1.0}])
adapter.connect()
try:
    adapter.poll()
    message = None
except ValueError as exc:
    message = str(exc)
adapter.close()
check(message is not None and "isn't a register address" in message,
      f"a tag that can't be a register address says so, instead of blaming the PLC (got {message!r})")

listener.close()
adapter = ModbusTCPAdapter({"host": "127.0.0.1", "port": port, "unit_id": 1, "timeout_s": 1},
                           [{"raw_tag": "40001", "canonical_metric": "weight_g", "data_type": "int", "scale_factor": 1.0}])
try:
    adapter.connect()
    adapter.poll()
    message = None
except ConnectionError as exc:
    message = str(exc)
adapter.close()
check(message is not None, f"a PLC that's gone raises instead of returning an empty reading (got {message!r})")

# --- serial: an unplugged adapter stops repeating the last weight -------------------
import serial  # noqa: E402

from device_gateway.adapters.serial_ascii import SerialASCIIAdapter  # noqa: E402


class UnpluggedPort:
    def readline(self):
        raise serial.SerialException("ClearCommError failed (PermissionError(13, 'The device does not recognize the command.'))")

    def close(self):
        pass


scale = SerialASCIIAdapter({"port": "COM9"}, [{"raw_tag": r"(?P<value>[-\d.]+)", "canonical_metric": "weight_g",
                                               "data_type": "float", "scale_factor": 1.0}])
scale._apply_line("  118.045 g")
scale.serial = UnpluggedPort()
scale._reader_loop()
try:
    scale.poll()
    message = None
except ConnectionError as exc:
    message = str(exc)
check(message is not None and "lost COM9" in message, f"a scale whose port vanished raises instead of repeating 118.045 g (got {message!r})")

# --- MQTT: a broker that's gone is noticed ----------------------------------------------
from device_gateway.adapters.mqtt_client import MQTTAdapter  # noqa: E402


class FakeClient:
    def subscribe(self, topic):
        pass


mqtt = MQTTAdapter({"host": "10.0.0.5", "port": 1883}, [{"raw_tag": "plant/pump3/weight", "canonical_metric": "weight_g",
                                                         "data_type": "float", "scale_factor": 1.0}])
mqtt._on_connect(FakeClient(), None, {}, 0)
check(mqtt._read_raw() == {}, "a connected broker with no message yet is just an empty reading")
mqtt._on_disconnect(None, None, 1)
mqtt._disconnected_since -= 60
try:
    mqtt._read_raw()
    message = None
except ConnectionError as exc:
    message = str(exc)
check(message is not None and "not connected to the broker" in message, f"a broker gone for a minute raises (got {message!r})")
mqtt._on_connect(FakeClient(), None, {}, 5)
try:
    mqtt._read_raw()
    message = None
except ConnectionError as exc:
    message = str(exc)
check(message is not None and "refused the connection" in message, f"a refused login says to check the username/password (got {message!r})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} GATEWAY SERVICE CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} GATEWAY SERVICE ASSERTIONS PASSED")
sys.stdout.flush()
os._exit(1 if FAILS else 0)
