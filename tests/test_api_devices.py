"""Device Gateway, ported from pages/Device_Registry.py: register a machine,
assign it to a pump/reactor, map its raw tags to canonical metrics.

Discovery endpoints (serial ports, subnet guess, network scan) do real local
I/O - a serial-port enumeration and a TCP probe of the machine's own loopback
range, both read-only and bounded, so they're exercised for real here rather
than skipped. test_device_connection against an unreachable address is
exercised too, to prove the bounded-timeout wrapper actually returns instead
of hanging - not against a real device, since none exists in this scratch
environment.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import api.main  # noqa: E402

FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(label)
        print(f"  FAIL  {label}")


client = TestClient(api.main.app)
CSRF = {"x-mes-client": "1"}

print("=" * 66)
print("API DEVICES: the Device Gateway registry")
print("=" * 66)

# --- access control: role, then the gateway switch itself ------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/devices")
check(r.status_code == 403, f"an operator is refused outright (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin account can log in (got {r.status_code})")

r = client.get("/api/devices/meta")
check(r.status_code == 200, f"meta loads on admin-console access alone, gateway off or not (got {r.status_code})")
check(r.json()["gateway_enabled"] is False, "...and honestly reports the gateway is off on a fresh plant")

r = client.get("/api/devices")
check(r.status_code == 403, f"the device list itself is refused while the gateway switch is off (got {r.status_code})")
check("switched off" in r.json()["detail"], f"...with a message that says why, not a bare Forbidden (got {r.json()})")

# --- turn the gateway on ----------------------------------------------------
r = client.put("/api/admin/settings", json={
    "shift_1_start": "06:00", "shift_1_hours": 8.0, "shift_1_break_mins": 60,
    "shift_2_start": "14:00", "shift_2_hours": 8.0, "shift_2_break_mins": 60,
    "shift_count": 2, "target_lph": 400.0, "yield_target_pct": 99.0,
    "enable_packing": True, "enable_bulk_pour": False, "enable_device_gateway": True,
    "operating_days": [0, 1, 2, 3, 4], "use_work_orders": False,
    "pump_form_url": "", "pump_form_label": "",
}, headers=CSRF)
check(r.status_code == 200, f"flipping the gateway on succeeds (got {r.status_code})")
check(client.get("/api/devices/meta").json()["gateway_enabled"] is True, "meta now reports it on")

r = client.get("/api/devices")
check(r.status_code == 200 and r.json() == [], f"the registry starts empty (got {r.json() if r.status_code == 200 else r.status_code})")

meta = client.get("/api/devices/meta").json()
check("modbus_tcp" in meta["protocol_labels"] and "mqtt" in meta["protocol_labels"],
      f"every protocol the gateway supports is listed (got {list(meta['protocol_labels'])})")
check("weight_g" in meta["canonical_metrics"], f"the canonical metric catalogue came through (got {meta['canonical_metrics']})")
check(any(p["name"] == "New Pump #1" for p in meta["pumps"]), f"the seeded pump shows up as an assignment option (got {meta['pumps']})")

# --- create / duplicate ----------------------------------------------------
r = client.post("/api/devices", json={
    "device_name": "Test Scale", "device_role": "scale", "protocol": "modbus_tcp",
    "connection": {"host": "10.0.0.50", "port": 502, "unit_id": 1}, "poll_interval_s": 5.0,
    "pump_station_id": None, "reactor_id": None, "notes": "",
}, headers=CSRF)
check(r.status_code == 201, f"registering a device succeeds (got {r.status_code})")
device = r.json()
check(device["status"] == "Unknown" and device["is_enabled"] is True,
      f"a fresh device starts enabled with an unknown status - nothing has polled it yet (got {device})")

r = client.post("/api/devices", json={
    "device_name": "Test Scale", "device_role": "scale", "protocol": "modbus_tcp",
    "connection": {"host": "10.0.0.51", "port": 502, "unit_id": 1},
}, headers=CSRF)
check(r.status_code == 409, f"a duplicate device name is refused, not silently created twice (got {r.status_code})")

r = client.post("/api/devices", json={"device_name": "  ", "device_role": "scale", "protocol": "modbus_tcp", "connection": {}}, headers=CSRF)
check(r.status_code == 400, f"a blank device name is refused (got {r.status_code})")

devices = client.get("/api/devices").json()
check(len(devices) == 1 and devices[0]["device_name"] == "Test Scale", f"the registry now holds exactly the one device (got {devices})")

# --- tag map ---------------------------------------------------------------
device_id = device["id"]
r = client.get(f"/api/devices/{device_id}/tags")
check(r.status_code == 200 and r.json() == [], f"no tags mapped yet (got {r.json() if r.status_code == 200 else r.status_code})")

r = client.post(f"/api/devices/{device_id}/tags", json={
    "raw_tag": "40001", "canonical_metric": "weight_g", "data_type": "float", "scale_factor": 0.1, "unit": "g",
}, headers=CSRF)
check(r.status_code == 200, f"saving a tag mapping succeeds (got {r.status_code})")

r = client.post(f"/api/devices/{device_id}/tags", json={
    "raw_tag": "40001", "canonical_metric": "net_weight_g", "data_type": "float", "scale_factor": 0.01, "unit": "g",
}, headers=CSRF)
check(r.status_code == 200, f"saving the SAME raw tag again succeeds (got {r.status_code})")
tags = client.get(f"/api/devices/{device_id}/tags").json()
check(len(tags) == 1 and tags[0]["canonical_metric"] == "net_weight_g" and tags[0]["scale_factor"] == 0.01,
      f"...and it overwrote the row rather than creating a second one (got {tags})")

r = client.post(f"/api/devices/{device_id}/tags", json={"raw_tag": "  ", "canonical_metric": "weight_g"}, headers=CSRF)
check(r.status_code == 400, f"a blank raw tag is refused (got {r.status_code})")

# A tag saved with no unit stores a real SQL NULL, which pandas reads back as
# float('nan') rather than None - the same trap this migration has hit
# before (see api/routers/admin.py's _opt / reactors.py's _s). A blank unit
# must not 500 the whole tag list.
r = client.post(f"/api/devices/{device_id}/tags", json={"raw_tag": "40002", "canonical_metric": "units_poured_total", "data_type": "int", "scale_factor": 1.0, "unit": ""}, headers=CSRF)
check(r.status_code == 200, f"saving a tag with no unit succeeds (got {r.status_code})")
r = client.get(f"/api/devices/{device_id}/tags")
check(r.status_code == 200, f"listing tags with a NULL unit in the mix doesn't 500 (got {r.status_code})")
no_unit_row = next((t for t in r.json() if t["raw_tag"] == "40002"), None)
check(no_unit_row is not None and no_unit_row["unit"] is None, f"the NULL unit comes back as None, not the string 'nan' (got {no_unit_row})")
client.delete(f"/api/devices/tags/{no_unit_row['id']}", headers=CSRF)

tag_id = tags[0]["id"]
r = client.delete(f"/api/devices/tags/{tag_id}", headers=CSRF)
check(r.status_code == 200, f"deleting a tag mapping succeeds (got {r.status_code})")
check(client.get(f"/api/devices/{device_id}/tags").json() == [], "...and it's actually gone")

# --- readings (empty - nothing has polled it in this scratch environment) --
r = client.get(f"/api/devices/{device_id}/readings?hours=24")
check(r.status_code == 200 and r.json() == [], f"no readings yet, and that's a normal empty list, not an error (got {r.json() if r.status_code == 200 else r.status_code})")

# --- enable / disable / delete ----------------------------------------------
r = client.put(f"/api/devices/{device_id}/enabled?enabled=false", headers=CSRF)
check(r.status_code == 200, f"disabling a device succeeds (got {r.status_code})")
check(client.get("/api/devices").json()[0]["is_enabled"] is False, "...and the registry reflects it")

r = client.put("/api/devices/999999/enabled?enabled=true", headers=CSRF)
check(r.status_code == 404, f"toggling a device that doesn't exist 404s (got {r.status_code})")

r = client.delete(f"/api/devices/{device_id}", headers=CSRF)
check(r.status_code == 200, f"deleting a device succeeds (got {r.status_code})")
check(client.get("/api/devices").json() == [], "...and the registry is empty again")

# --- test connection: a real bounded attempt against nothing listening -----
r = client.post("/api/devices/test-connection", json={
    "protocol": "modbus_tcp", "connection": {"host": "127.0.0.1", "port": 1, "unit_id": 1, "timeout_s": 1}, "probe_tags": [],
}, headers=CSRF)
check(r.status_code == 200, f"the test-connection endpoint itself returns cleanly rather than 500ing (got {r.status_code})")
check(r.json()["ok"] is False and r.json()["error"], f"nothing is listening on that port, so it reports a real failure (got {r.json()})")

# --- discovery: real, read-only, local-only I/O -----------------------------
r = client.get("/api/devices/discovery/serial-ports")
check(r.status_code == 200 and isinstance(r.json(), list), f"serial port enumeration returns a list without erroring (got {r.status_code})")

r = client.get("/api/devices/discovery/subnet")
check(r.status_code == 200 and "/" in r.json()["subnet"], f"a CIDR subnet guess comes back (got {r.json() if r.status_code == 200 else r.status_code})")

r = client.get("/api/devices/discovery/scan?subnet=127.0.0.1/30")
check(r.status_code == 200 and isinstance(r.json(), list), f"a tiny, fast scan of loopback completes and returns a list (got {r.status_code})")

r = client.get("/api/devices/discovery/scan?subnet=not-a-subnet")
check(r.status_code == 400, f"a malformed subnet is refused with a real error, not a crash (got {r.status_code})")

# --- simulator: the no-hardware protocol, and its tag map auto-seed --------
r = client.post("/api/devices", json={
    "device_name": "Sim Pump", "device_role": "filling_station", "protocol": "simulator",
    "connection": {"sim_profile": "pump", "cycle_seconds": 1.0, "target_weight_g": 400, "noise_pct": 0},
    "poll_interval_s": 1.0,
}, headers=CSRF)
check(r.status_code == 201, f"registering a simulator device succeeds like any other protocol (got {r.status_code})")
sim_device = r.json()

tags = client.get(f"/api/devices/{sim_device['id']}/tags").json()
tag_names = {t["canonical_metric"] for t in tags}
check({"units_poured_delta", "weight_g", "machine_state", "fault_code"} <= tag_names,
      f"a pump-profile simulator gets a full tag map for free, no manual mapping needed (got {tag_names})")

r = client.post("/api/devices", json={
    "device_name": "Sim Scale", "device_role": "scale", "protocol": "simulator",
    "connection": {"sim_profile": "scale", "target_weight_g": 120}, "poll_interval_s": 1.0,
}, headers=CSRF)
check(r.status_code == 201, f"a scale-profile simulator device saves too (got {r.status_code})")
sim_scale = r.json()
scale_tags = {t["canonical_metric"] for t in client.get(f"/api/devices/{sim_scale['id']}/tags").json()}
check(scale_tags == {"weight_g"}, f"a scale profile only auto-maps weight_g, not the pump-only metrics (got {scale_tags})")

# The API's own test-connection endpoint builds an adapter straight from a
# plain connection dict (device_crud.test_device_connection -> build_adapter)
# and never touches connection_json's Fernet encryption at all - so it can't
# prove the actual background gateway (service.py) can read a SAVED device
# back. build_adapter_from_device is the one real code path that does that,
# and it has to go through decrypt_connection(), not a bare json.loads() -
# exercised directly here against the real ORM row this API call produced,
# which is the only way to catch that class of bug at all.
from device_gateway.registry import build_adapter_from_device  # noqa: E402
from db_core import ScopedSession  # noqa: E402
from device_models import Device, DeviceTagMap  # noqa: E402

session = ScopedSession()
device_row = session.get(Device, sim_device["id"])
tag_rows = session.query(DeviceTagMap).filter(DeviceTagMap.device_id == sim_device["id"]).all()
_ = (device_row.connection_json, device_row.protocol)  # force-load before the session below closes it
for t in tag_rows:
    _ = (t.raw_tag, t.canonical_metric, t.data_type, t.scale_factor)
session.close()

try:
    adapter = build_adapter_from_device(device_row, tag_rows)
    adapter.connect()
    mapped = adapter.poll()
    adapter.close()
    poll_ok, poll_err = True, None
except Exception as exc:
    poll_ok, poll_err = False, str(exc)
check(poll_ok, f"a saved device's ENCRYPTED connection_json decrypts and polls through the real gateway code path (got error: {poll_err})")
check(poll_ok and "weight_g" in mapped, f"...and comes back with the mapped canonical metrics (got {mapped if poll_ok else None})")

client.delete(f"/api/devices/{sim_device['id']}", headers=CSRF)
client.delete(f"/api/devices/{sim_scale['id']}", headers=CSRF)

# --- 4.07: gateway check-ins, honest status, UTC timestamps -----------------
import os  # noqa: E402
from datetime import datetime  # noqa: E402

import device_crud  # noqa: E402
from device_models import DeviceReading, GatewayJob  # noqa: E402
from sqlalchemy import text  # noqa: E402

check("server_hostname" in client.get("/api/devices/meta").json(), "meta names the server, so the page can say where a scan runs")

r = client.get("/api/devices/gateways")
check(r.status_code == 200 and r.json() == [], f"no gateway has checked in on a fresh plant (got {r.json() if r.status_code == 200 else r.status_code})")

r = client.post("/api/devices", json={
    "device_name": "Status PLC", "device_role": "filling_station", "protocol": "modbus_tcp",
    "connection": {"host": "10.0.0.60", "port": 502, "unit_id": 1}, "poll_interval_s": 2.0,
}, headers=CSRF)
status_id = r.json()["id"]


def set_device(sql_fragment, **params):
    session = ScopedSession()
    try:
        session.execute(text(f"UPDATE devices SET {sql_fragment} WHERE id = :id"), {"id": status_id, **params})
        session.commit()
    finally:
        session.close()


def status_row():
    return next(d for d in client.get("/api/devices").json() if d["id"] == status_id)


row = status_row()
check(row["status"] == "Not reporting" and "No gateway PC has checked in yet" in (row["last_error"] or ""),
      f"a device nothing is polling says so, instead of a bare Unknown (got {row})")

# A device the gateway last marked Online, freshly seen - Online, whatever the
# check-ins say, so a pre-4.07 gateway that doesn't check in still reads right.
set_device("status = 'Online', last_error = NULL, last_seen_at = timezone('utc', now())")
row = status_row()
check(row["status"] == "Online", f"a freshly seen device is Online even with no check-ins (got {row})")
check(row["last_seen_at"].endswith("+00:00"), f"last_seen_at carries its UTC offset for the browser (got {row['last_seen_at']})")
check(row["seconds_since_seen"] is not None and row["seconds_since_seen"] < 5, f"...and the age comes from the database clock (got {row['seconds_since_seen']})")

# The gateway died ten minutes ago: that same stored Online must not show.
set_device("last_seen_at = timezone('utc', now()) - interval '10 minutes'")
row = status_row()
check(row["status"] == "Not reporting", f"a device the gateway last called Online, unseen for 10 min, is Not reporting (got {row})")

device_crud.record_gateway_heartbeat("TEST-GATEWAY", "10.0.0.5", "PT-V4.07", datetime.utcnow())
nodes = client.get("/api/devices/gateways").json()
check(len(nodes) == 1 and nodes[0]["hostname"] == "TEST-GATEWAY" and nodes[0]["online"],
      f"a check-in shows the gateway as running (got {nodes})")
check(nodes[0]["last_heartbeat_at"].endswith("+00:00"), f"check-in times carry their UTC offset (got {nodes[0]['last_heartbeat_at']})")
row = status_row()
check(row["status"] == "Not reporting" and "stuck waiting on this device" in (row["last_error"] or ""),
      f"with the gateway running, a silent device is blamed on the device (got {row})")

session = ScopedSession()
session.execute(text("UPDATE gateway_nodes SET last_heartbeat_at = timezone('utc', now()) - interval '30 seconds'"))
session.commit()
session.close()
row = status_row()
check("hasn't checked in for" in (row["last_error"] or ""),
      f"a gateway that has just missed check-ins is suspected before the device is (got {row['last_error']!r})")

session = ScopedSession()
session.execute(text("UPDATE gateway_nodes SET last_heartbeat_at = timezone('utc', now()) - interval '2 hours'"))
session.commit()
session.close()
row = status_row()
check(row["status"] == "Not reporting" and "No gateway PC has checked in for 2 h" in (row["last_error"] or ""),
      f"a gateway gone for 2 h is named as the reason (got {row['last_error']!r})")
check(client.get("/api/devices/gateways").json()[0]["online"] is False, "...and the gateway list shows it offline")

set_device("status = 'Error', last_error = 'Modbus TCP: no response from 10.0.0.60:502'")
row = status_row()
check(row["status"] == "Not reporting" and "Last error before it stopped: Modbus TCP: no response" in (row["last_error"] or ""),
      f"an Error left behind by a gateway that has since stopped points at the gateway, keeping the old error (got {row})")
device_crud.record_gateway_heartbeat("TEST-GATEWAY", "10.0.0.5", "PT-V4.07", datetime.utcnow())
row = status_row()
check(row["status"] == "Error" and row["last_error"].startswith("Modbus TCP: no response"),
      f"with the gateway running, a device error is shown as it is (got {row})")

client.put(f"/api/devices/{status_id}/enabled?enabled=false", headers=CSRF)
set_device("status = 'Online', last_seen_at = timezone('utc', now()) - interval '1 day'")
check(status_row()["status"] == "Online", "a disabled device isn't relabelled - nothing is expected of it")

device_crud.record_gateway_heartbeat("TEST-GATEWAY", "10.0.0.5", "PT-V4.07", datetime.utcnow())

# --- readings carry a UTC offset too ------------------------------------------
session = ScopedSession()
session.add(DeviceReading(device_id=status_id, timestamp=datetime.utcnow(), metric="weight_g", value_numeric=851.5))
session.commit()
session.close()
r = client.get(f"/api/devices/{status_id}/readings?hours=1")
check(r.status_code == 200 and r.json() and r.json()[0]["timestamp"].endswith("+00:00"),
      f"reading timestamps carry their UTC offset (got {r.json() if r.status_code == 200 else r.status_code})")
client.delete(f"/api/devices/{status_id}", headers=CSRF)

# --- probe tags: Modbus reads one raw register unless told otherwise --------
probes = device_crud.probe_tag_map("modbus_tcp", ["40001", "40002:float", " 40010 : int32 ", ""])
check([(t["raw_tag"], t["data_type"]) for t in probes] == [("40001", "int"), ("40002", "float"), ("40010", "int32")],
      f"Modbus probes default to a single register, with :float / :int32 overrides (got {probes})")
probes = device_crud.probe_tag_map("opcua", ["ns=2;s=Machine:Weight"])
check(probes[0]["raw_tag"] == "ns=2;s=Machine:Weight", f"a colon in a non-Modbus tag is left alone (got {probes})")

# --- gateway jobs --------------------------------------------------------------
from device_gateway.jobs import run_job  # noqa: E402
from gateway_crypto import KeyMismatchError  # noqa: E402

r = client.post("/api/devices/gateways/NO-SUCH-PC/jobs", json={"kind": "serial_ports", "params": {}}, headers=CSRF)
check(r.status_code == 404, f"a job for a gateway that never checked in is refused (got {r.status_code})")
r = client.post("/api/devices/gateways/TEST-GATEWAY/jobs", json={"kind": "format_disk", "params": {}}, headers=CSRF)
check(r.status_code == 400, f"an unknown job kind is refused (got {r.status_code})")
r = client.post("/api/devices/gateways/TEST-GATEWAY/jobs", json={"kind": "scan", "params": {"subnet": "not-a-subnet"}}, headers=CSRF)
check(r.status_code == 400, f"a malformed subnet is refused before it ever reaches the gateway (got {r.status_code})")

r = client.post("/api/devices/gateways/TEST-GATEWAY/jobs", json={"kind": "serial_ports", "params": {}}, headers=CSRF)
check(r.status_code == 201, f"a serial-port job for a known gateway is accepted (got {r.status_code})")
job_id = r.json()["id"]
check(client.get(f"/api/devices/gateway-jobs/{job_id}").json()["status"] == "pending", "...and waits as pending")
check(device_crud.claim_next_gateway_job("SOME-OTHER-PC") is None, "a different gateway doesn't take a job addressed to someone else")
job = device_crud.claim_next_gateway_job("TEST-GATEWAY")
check(job is not None and job["id"] == job_id, f"the addressed gateway claims it (got {job})")
check(device_crud.claim_next_gateway_job("TEST-GATEWAY") is None, "...only once")
check(client.get(f"/api/devices/gateway-jobs/{job_id}").json()["status"] == "running", "...and it shows as running")
device_crud.finish_gateway_job(job_id, result=run_job(job["kind"], device_crud.decode_gateway_job_params(job)))
done = client.get(f"/api/devices/gateway-jobs/{job_id}").json()
check(done["status"] == "done" and isinstance(done["result"], list), f"the gateway's answer comes back to the page (got {done})")

r = client.post("/api/devices/gateways/TEST-GATEWAY/jobs", json={"kind": "test_connection", "params": {
    "protocol": "mqtt", "connection": {"host": "10.0.0.9", "password": "s3cret-broker-pw"}, "probe_tags": []}}, headers=CSRF)
job_id = r.json()["id"]
session = ScopedSession()
stored = session.get(GatewayJob, job_id).request_json
session.close()
check("s3cret-broker-pw" not in stored, "a Test Connection job's password is encrypted while it waits in the database")
job = device_crud.claim_next_gateway_job("TEST-GATEWAY")
check(device_crud.decode_gateway_job_params(job)["connection"]["password"] == "s3cret-broker-pw", "...and the gateway can read it back")

real_key = os.environ.get("GATEWAY_ENCRYPTION_KEY")
from cryptography.fernet import Fernet  # noqa: E402
os.environ["GATEWAY_ENCRYPTION_KEY"] = Fernet.generate_key().decode()
try:
    device_crud.decode_gateway_job_params(job)
    mismatch = None
except KeyMismatchError as exc:
    mismatch = str(exc)
finally:
    os.environ["GATEWAY_ENCRYPTION_KEY"] = real_key
check(mismatch is not None and "GATEWAY_ENCRYPTION_KEY" in mismatch and "MES PC" in mismatch,
      f"a gateway with a different key gets a sentence saying what to copy where (got {mismatch!r})")
device_crud.finish_gateway_job(job_id, error=mismatch)
session = ScopedSession()
check(session.get(GatewayJob, job_id).request_json is None, "a finished job's request - password included - is cleared")
session.close()

r = client.post("/api/devices/gateways/TEST-GATEWAY/jobs", json={"kind": "subnet", "params": {}}, headers=CSRF)
job_id = r.json()["id"]
session = ScopedSession()
session.execute(text("UPDATE gateway_jobs SET created_at = timezone('utc', now()) - interval '5 minutes' WHERE id = :id"), {"id": job_id})
session.commit()
session.close()
job = client.get(f"/api/devices/gateway-jobs/{job_id}").json()
check(job["status"] == "error" and "didn't pick this up" in (job["error"] or ""),
      f"a job no gateway picks up ends with a reason instead of spinning forever (got {job})")
check(device_crud.claim_next_gateway_job("TEST-GATEWAY") is None, "...and a gateway that turns up late doesn't run it")

# --- everything here requires a session ------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/devices/meta")
check(r.status_code == 401, f"device gateway meta refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API DEVICES CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API DEVICES ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
