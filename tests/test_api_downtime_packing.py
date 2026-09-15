"""Downtime and Packing - the two simplest tabs in the pilot, ported from
pages/operator_form/downtime_tab.py and packing_tab.py verbatim. Neither
has a lot gate or changeover logic, so there's less to prove here than the
Pouring tab needed - mainly that the write actually lands and that the
role/ability boundaries around it are unchanged.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import api.main  # noqa: E402
import crud  # noqa: E402

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
print("API DOWNTIME + PACKING")
print("=" * 66)

r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")

# --- downtime ----------------------------------------------------------
before = len(crud.get_production_logs_df(operator="Demo Operator"))  # sanity: downtime isn't a ProductionLog
r = client.post("/api/downtime/submit", json={
    "station": "New Pump #1", "reason": "Break/Shift Change", "duration_min": 15,
    "notes": "Cleaned dispensing valve nozzle.",
}, headers=CSRF)
check(r.status_code == 200, f"a downtime event submits (got {r.status_code}, {r.text[:200]})")
check("15 minutes" in r.json()["message"], f"the response names the duration (got {r.json()})")
after = len(crud.get_production_logs_df(operator="Demo Operator"))
check(before == after, "downtime never writes a ProductionLog row - it's its own table")

downtime_df = crud.get_downtime_logs_df()
check(len(downtime_df) == 1, "exactly one downtime row exists now")
check(downtime_df.iloc[0]["operator_name"] == "Demo Operator", "...attributed to the signed-in operator")
check(downtime_df.iloc[0]["duration_min"] == 15, "...with the duration actually submitted")

r = client.post("/api/downtime/submit", json={
    "station": "New Pump #1", "reason": "Break/Shift Change", "duration_min": 0,
}, headers=CSRF)
check(r.status_code == 422, f"a non-positive duration is rejected by validation (got {r.status_code})")

# --- packing -------------------------------------------------------------
r = client.post("/api/packing/submit", json={
    "cartridge_type": "V2", "resin": "Standard Clear V5", "lot_number": "LOT-20260913-01",
    "units_packed": 480, "notes": "2 partial boxes added to skid.",
}, headers=CSRF)
check(r.status_code == 200, f"a packing count submits (got {r.status_code}, {r.text[:200]})")
check("480 units" in r.json()["message"], f"the response names the count (got {r.json()})")

logs = crud.get_production_logs_df(operator="Demo Operator")
pack_row = logs[logs["log_type"] == "Packing Count"].iloc[0]
check(pack_row["pump_station"] == "Pack-Out Station", "packing always logs against Pack-Out Station")
check(int(pack_row["bottles_filled"]) == 480, "...with the units actually packed")
check(pack_row["scrap_empty"] == 0 and pack_row["scrap_filled"] == 0,
      "packing never carries scrap - it's not part of that form")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.post("/api/downtime/submit", json={"station": "New Pump #1", "reason": "x", "duration_min": 5},
                headers=CSRF)
check(r.status_code == 401, f"downtime submit refuses an anonymous request (got {r.status_code})")
r = client.post("/api/packing/submit", json={"cartridge_type": "V2", "resin": "x", "lot_number": "x",
                                             "units_packed": 1}, headers=CSRF)
check(r.status_code == 401, f"packing submit refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API DOWNTIME/PACKING CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API DOWNTIME/PACKING ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
