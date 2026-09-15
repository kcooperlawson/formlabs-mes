"""Log Management & Data Cleanup, ported from pages/Mgr_Log_Management.py:
filtering, single-row delete, and bulk-delete for production and downtime
logs. Gated by manage_logs on every route, including the reads.
"""
import pathlib
import sys
from datetime import date, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import crud  # noqa: E402
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
print("API LOG MANAGEMENT: finding and cleaning up bad log entries")
print("=" * 66)

# --- gated behind manage_logs, not a bare role check ------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/log-management/production")
check(r.status_code == 403, f"an operator without manage_logs is refused even the read (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/log-management/production")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- empty reads as empty, not broken ---------------------------------------
r = client.get("/api/log-management/production")
check(r.status_code == 200, f"loads with nothing logged (got {r.status_code})")
check(r.json() == {"filters": {"log_types": [], "pumps": [], "operators": [], "min_date": None, "max_date": None},
                   "total_matches": 0, "rows": []},
      f"zero everything with nothing logged (got {r.json()})")

r = client.get("/api/log-management/downtime")
check(r.json()["total_matches"] == 0, "downtime reads as empty too")

# --- seed a realistic mix of production logs --------------------------------
today = date.today()
crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=100, scrap_empty=0, scrap_filled=0, log_type="Hourly Bottle Count")
crud.add_hourly_log("Sasha", "New Pump #2", "Shift 1", "V1", "Standard Black V5", "L2",
                    bottles=50, scrap_empty=0, scrap_filled=0, log_type="Hourly Bottle Count")
crud.add_hourly_log("Demo Operator", "Pack-Out Station", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=80, scrap_empty=0, scrap_filled=0, log_type="Packing Count")
crud.add_downtime_log("Demo Operator", "New Pump #1", "Shift 1", "Changeover", 20)
crud.add_downtime_log("Sasha", "New Pump #2", "Shift 1", "Resin Spill", 10)

r = client.get("/api/log-management/production")
body = r.json()
check(body["total_matches"] == 3, f"every production log is found with no filters (got {body['total_matches']})")
check(set(body["filters"]["log_types"]) == {"Hourly Bottle Count", "Packing Count"},
      f"log-type options come from everything logged (got {body['filters']['log_types']})")
check(set(body["filters"]["operators"]) == {"Demo Operator", "Sasha"}, "operator options list everyone")
sasha_row = next(r for r in body["rows"] if r["operator_name"] == "Sasha")
check(sasha_row["resin_color"] != "" and sasha_row["resin_color"] is not None,
      "each row carries its resin's colour, resolved the same way everywhere else")

# --- filters actually filter -------------------------------------------
r = client.get("/api/log-management/production", params={"log_type": "Packing Count"})
check(r.json()["total_matches"] == 1, f"log-type filter narrows correctly (got {r.json()['total_matches']})")

r = client.get("/api/log-management/production", params={"operator": "Sasha"})
check(r.json()["total_matches"] == 1 and r.json()["rows"][0]["operator_name"] == "Sasha",
      "operator filter narrows correctly")

r = client.get("/api/log-management/production", params={"pump_station": "New Pump #1"})
check(r.json()["total_matches"] == 1, "pump filter narrows correctly")

old_day = today - timedelta(days=10)
r = client.get("/api/log-management/production", params={"start_date": str(old_day), "end_date": str(old_day)})
check(r.json()["total_matches"] == 0, "a date range with nothing in it correctly finds nothing")

r = client.get("/api/log-management/production", params={"limit": 1})
check(len(r.json()["rows"]) == 1 and r.json()["total_matches"] == 3,
      f"the display limit slices rows without changing the reported match total (got {r.json()})")

# --- single-row delete, and that it re-syncs work orders --------------------
crud.add_reactor("Reactor 1", 5000)
run_auto = crud.create_assigned_run(
    reactor_id="Reactor 1", reactor_size_l=5000, resin_type="Standard Clear V5", cartridge_type="V2",
    target_units=1000, assigned_operator="Demo Operator", pump_station="New Pump #1", lot_number="L1", notes="")
check(run_auto == 100, f"the run auto-detects the 100 units already poured on that pump/resin/lot (got {run_auto})")

target_row = next(r for r in body["rows"] if r["pump_station"] == "New Pump #1")
r = client.delete(f"/api/log-management/production/{target_row['id']}", headers=CSRF)
check(r.status_code == 200, f"deleting an existing production log succeeds (got {r.status_code})")

runs_after = crud.get_assigned_runs_df()
check(runs_after.iloc[0]["current_units"] == 0,
      f"deleting the log it was counted against re-syncs the run's progress back down (got {runs_after.iloc[0]['current_units']})")

r = client.delete("/api/log-management/production/999999", headers=CSRF)
check(r.status_code == 404, f"deleting a nonexistent production log is refused (got {r.status_code})")

# --- bulk delete only touches what's currently matched ----------------------
r = client.post("/api/log-management/production/bulk-delete", params={"pump_station": "New Pump #2"}, headers=CSRF)
check(r.status_code == 200 and r.json()["deleted"] == 1, f"bulk delete removes exactly the matched rows (got {r.json()})")
r = client.get("/api/log-management/production")
check(r.json()["total_matches"] == 1, f"...and leaves everything else alone (got {r.json()['total_matches']})")

# --- downtime: filters, delete, bulk delete ---------------------------------
r = client.get("/api/log-management/downtime", params={"reason": "Resin Spill"})
check(r.json()["total_matches"] == 1, "downtime reason filter narrows correctly")

r = client.get("/api/log-management/downtime")
dt_id = r.json()["rows"][0]["id"] if r.json()["rows"][0]["reason"] == "Changeover" else r.json()["rows"][1]["id"]
r = client.delete(f"/api/log-management/downtime/{dt_id}", headers=CSRF)
check(r.status_code == 200, f"deleting an existing downtime log succeeds (got {r.status_code})")
r = client.delete("/api/log-management/downtime/999999", headers=CSRF)
check(r.status_code == 404, f"deleting a nonexistent downtime log is refused (got {r.status_code})")

r = client.post("/api/log-management/downtime/bulk-delete", headers=CSRF)
check(r.status_code == 200 and r.json()["deleted"] == 1, f"bulk delete with no filters removes everything remaining (got {r.json()})")
r = client.get("/api/log-management/downtime")
check(r.json()["total_matches"] == 0, "downtime is now empty")

# --- writes require the ability too, not just the reads ---------------------
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
r = client.delete("/api/log-management/production/1", headers=CSRF)
check(r.status_code == 403, f"an operator cannot delete a production log either (got {r.status_code})")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/log-management/production")
check(r.status_code == 401, f"log-management refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API LOG MANAGEMENT CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API LOG MANAGEMENT ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
