"""Fleet Production Progress & Work Order Dispatch, ported from
pages/Mgr_Assigned_Runs.py: dispatch, progress, status, delete,
custom-complete-with-reconciliation, and sync-with-logs.
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
print("API ASSIGNED RUNS: Fleet Production Progress & Work Order Dispatch")
print("=" * 66)

crud.add_reactor("Reactor 1", 5000)

# --- gated behind view_manager_cockpit for every action, not just reads ----
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/assigned-runs")
check(r.status_code == 403, f"an operator without view_manager_cockpit is refused the read (got {r.status_code})")
r = client.post("/api/assigned-runs", json={
    "run_type": "Pouring", "reactor_id": "Reactor 1", "reactor_size_l": 5000,
    "cartridge_type": "V2", "resin_type": "Standard Clear V5", "target_units": 100,
    "assigned_pump": "New Pump #1", "assigned_operator": "Demo Operator", "lot_number": "L1",
}, headers=CSRF)
check(r.status_code == 403, f"...nor dispatch a run (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/assigned-runs")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- options for the dispatch form ------------------------------------------
r = client.get("/api/assigned-runs/options")
check(r.status_code == 200, f"dispatch options load (got {r.status_code})")
opts = r.json()
check(any(x["reactor_name"] == "Reactor 1" for x in opts["reactors"]), "the seeded reactor is offered")
check("Demo Operator" in opts["operators"], "operator personnel are listed")
check("Demo Operator" not in opts["packers"], "...but not mixed into the packer list")

# --- an empty fleet reads as empty, not broken ------------------------------
r = client.get("/api/assigned-runs")
check(r.status_code == 200, f"loads with nothing dispatched (got {r.status_code})")
body = r.json()
check(body["totals"]["total_target"] == 0 and body["totals"]["fleet_pct"] == 0.0,
      f"zero fleet progress, not a divide-by-zero, with nothing dispatched (got {body['totals']})")
check(body["runs"] == [], "no runs yet")

# --- dispatching a new run -----------------------------------------------
r = client.post("/api/assigned-runs", json={
    "run_type": "Pouring", "reactor_id": "Reactor 1", "reactor_size_l": 5000,
    "cartridge_type": "V2", "resin_type": "Standard Clear V5", "target_units": 100,
    "assigned_pump": "New Pump #1", "assigned_operator": "Demo Operator", "lot_number": "L1",
    "status": "Active",
}, headers=CSRF)
check(r.status_code == 201, f"a well-formed dispatch saves (got {r.status_code}, {r.text[:150]})")

r = client.post("/api/assigned-runs", json={
    "run_type": "Pouring", "reactor_id": "Reactor 1", "reactor_size_l": 5000,
    "cartridge_type": "V2", "resin_type": "Standard Clear V5", "target_units": 100,
    "assigned_pump": "New Pump #1", "assigned_operator": "Demo Operator", "lot_number": "L1",
    "status": "Somewhere Else",
}, headers=CSRF)
check(r.status_code == 400, f"an unrecognized initial status is refused (got {r.status_code})")

r = client.get("/api/assigned-runs")
body = r.json()
check(len(body["runs"]) == 1, "the dispatched run shows up")
run = body["runs"][0]
run_id = run["id"]
check(run["status"] == "Active" and run["target_units"] == 100 and run["current_units"] == 0,
      f"it starts with zero progress against the target (got {run})")
check(run["resin_color"] != "", "the resin colour is resolved server-side, same as everywhere else")
check(body["totals"]["total_target"] == 100 and body["totals"]["active_count"] == 1,
      f"fleet totals reflect the one active run (got {body['totals']})")

# --- progress buttons, and that they survive a re-fetch (the auto-sync) -----
r = client.post(f"/api/assigned-runs/{run_id}/progress", json={"delta": 50}, headers=CSRF)
check(r.status_code == 200, f"+50 progress applies (got {r.status_code})")
r = client.get("/api/assigned-runs")
run = next(x for x in r.json()["runs"] if x["id"] == run_id)
check(run["current_units"] == 50, f"progress survives the auto-sync re-fetch (got {run['current_units']})")
adjustment_logs = crud.get_production_logs_df(operator="Plant Lead")
check(len(adjustment_logs) == 1 and adjustment_logs.iloc[0]["bottles_filled"] == 50,
      "a manual progress adjustment writes a real production log (attributed to whoever is signed in and "
      "clicked it, same as the original page's st.session_state user_name), so the sync has something to "
      "recompute from")

r = client.post(f"/api/assigned-runs/{run_id}/progress", json={"delta": 50}, headers=CSRF)
r = client.get("/api/assigned-runs")
run = next(x for x in r.json()["runs"] if x["id"] == run_id)
check(run["status"] == "Done" and run["current_units"] == 100,
      f"reaching the target auto-closes the run (got {run})")

# --- status toggle on a fresh queued run ------------------------------------
r = client.post("/api/assigned-runs", json={
    "run_type": "Pouring", "reactor_id": "Reactor 1", "reactor_size_l": 5000,
    "cartridge_type": "V1", "resin_type": "Standard Black V5", "target_units": 40,
    "assigned_pump": "New Pump #2", "assigned_operator": "Sasha", "lot_number": "L2",
    "status": "Queued",
}, headers=CSRF)
check(r.status_code == 201, f"a queued dispatch saves (got {r.status_code})")
r = client.get("/api/assigned-runs")
queued_run = next(x for x in r.json()["runs"] if x["lot_number"] == "L2")
check(queued_run["status"] == "Queued", "it starts queued, as requested")

r = client.post(f"/api/assigned-runs/{queued_run['id']}/status", json={"status": "Active"}, headers=CSRF)
check(r.status_code == 200, f"starting a queued run succeeds (got {r.status_code})")
r = client.post(f"/api/assigned-runs/{queued_run['id']}/status", json={"status": "Paused"}, headers=CSRF)
check(r.status_code == 400, f"an unrecognized status is refused (got {r.status_code})")

# --- custom-complete finalizes AND reconciles pouring to packing ------------
crud.add_hourly_log("Sasha", "New Pump #2", "Shift 1", "V1", "Standard Black V5", "L2",
                    bottles=30, scrap_empty=0, scrap_filled=0, log_type="Hourly Bottle Count")
before_recon = len(crud.get_production_logs_df())
r = client.post(f"/api/assigned-runs/{queued_run['id']}/complete", json={"final_units": 35}, headers=CSRF)
check(r.status_code == 200, f"a custom-total completion succeeds (got {r.status_code}, {r.text[:150]})")
after_recon = crud.get_production_logs_df()
check(len(after_recon) == before_recon + 1,
      "finalizing writes exactly one reconciliation log for the 5-unit variance")
recon_row = after_recon[after_recon["operator_name"] == "System Auto-Reconciliation"].iloc[0]
check(recon_row["bottles_filled"] == 5, f"...sized to the actual variance, not the full total (got {recon_row['bottles_filled']})")

r = client.get("/api/assigned-runs")
done_run = next(x for x in r.json()["runs"] if x["id"] == queued_run["id"])
check(done_run["status"] == "Done" and done_run["current_units"] == 35,
      f"the run itself carries the manually-entered final count (got {done_run})")

# --- sync-with-logs is callable and doesn't blow up on a mixed fleet -------
r = client.post("/api/assigned-runs/sync", headers=CSRF)
check(r.status_code == 200, f"sync-with-logs runs cleanly (got {r.status_code})")

# --- deleting a work order -------------------------------------------------
r = client.delete(f"/api/assigned-runs/{queued_run['id']}", headers=CSRF)
check(r.status_code == 200, f"deleting an existing work order succeeds (got {r.status_code})")
r = client.get("/api/assigned-runs")
check(all(x["id"] != queued_run["id"] for x in r.json()["runs"]), "the deleted work order is gone")

r = client.delete("/api/assigned-runs/999999", headers=CSRF)
check(r.status_code == 404, f"deleting a nonexistent work order is refused (got {r.status_code})")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/assigned-runs")
check(r.status_code == 401, f"assigned-runs refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API ASSIGNED RUNS CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API ASSIGNED RUNS ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
