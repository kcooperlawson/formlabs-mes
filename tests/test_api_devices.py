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
