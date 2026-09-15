"""Batch History, ported from pages/Mgr_Batch_History.py: reactor dwell time,
QC turnaround, and the QC-entry form moved here from the reactor page.
"""
import pathlib
import sys
from datetime import datetime, timedelta

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
print("API BATCH HISTORY: reactor dwell and QC turnaround")
print("=" * 66)

# --- gated behind view_manager_cockpit, not a bare role check --------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/batch-history")
check(r.status_code == 403, f"an operator without view_manager_cockpit is refused (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/batch-history")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- bad window values are rejected, not silently ignored -------------------
r = client.get("/api/batch-history", params={"days": 3})
check(r.status_code == 400, f"an unsupported window is refused (got {r.status_code})")

# --- an empty window reads as empty, not broken -----------------------------
r = client.get("/api/batch-history", params={"days": 30})
check(r.status_code == 200, f"loads with nothing logged (got {r.status_code})")
body = r.json()
check(body["totals"] == {"fillings_in_window": 0, "sitting_now": 0, "waiting_qc": 0,
                         "avg_qc_turnaround_h": None, "avg_time_in_vessel_h": None,
                         "longest_sitting_h": None, "longest_qc_wait_h": None, "no_qc_recorded": 0},
      f"zero everything, not an error, with nothing logged (got {body['totals']})")
check(body["can_manage_qc"] is True, "the seeded admin/manager account can manage QC")

# --- seed a realistic mix of fillings ---------------------------------------
now = datetime.now()

# Reactor 1: still sitting, no QC ever recorded on it.
id_open = crud.open_batch("Reactor 1", "Standard Clear V5", filled_at=now - timedelta(hours=10))

# Reactor 2: closed, 20 hours in the vessel, never sent to QC.
crud.open_batch("Reactor 2", "Standard Black V5", filled_at=now - timedelta(hours=40))
crud.close_batch("Reactor 2", emptied_at=now - timedelta(hours=20))

# Reactor 3: closed, currently out at QC (sent, no result yet).
id_at_qc = crud.open_batch("Reactor 3", "Standard Grey V5", filled_at=now - timedelta(hours=30))
crud.close_batch("Reactor 3", emptied_at=now - timedelta(hours=5))
ok, msg = crud.set_batch_qc(id_at_qc, sent_at=now - timedelta(hours=3))
check(ok, f"recording a QC send with no result yet succeeds (got {msg!r})")

# Reactor 1 again (a second, separate filling after the first would need to
# close first) - instead use a fourth vessel for a completed QC round trip.
id_done = crud.open_batch("Reactor 4", "Standard White V5", filled_at=now - timedelta(hours=15))
crud.close_batch("Reactor 4", emptied_at=now - timedelta(hours=2))
ok, msg = crud.set_batch_qc(id_done, sent_at=now - timedelta(hours=1, minutes=30),
                            result_at=now - timedelta(minutes=30), result="pass", by="Plant Lead")
check(ok, f"recording a completed QC round trip succeeds (got {msg!r})")

r = client.get("/api/batch-history", params={"days": 30})
check(r.status_code == 200, f"loads with real data (got {r.status_code})")
body = r.json()
t = body["totals"]
check(t["fillings_in_window"] == 4, f"every filling in the window counts (got {t})")
check(t["sitting_now"] == 1, "exactly one filling is still open (Reactor 1)")
check(t["waiting_qc"] == 1, "exactly one filling is out at QC (Reactor 3)")
check(t["no_qc_recorded"] == 1, "exactly one OPEN filling has no QC at all (Reactor 1)")
check(t["avg_qc_turnaround_h"] == 1.0, f"QC turnaround averages only completed round trips (got {t['avg_qc_turnaround_h']})")
check(t["longest_qc_wait_h"] == 3.0, f"longest wait matches the one open QC check (got {t['longest_qc_wait_h']})")

dwell = {d["reactor_name"]: d["avg_hours"] for d in body["dwell_by_vessel"]}
check(dwell.get("Reactor 2") == 20.0, f"dwell time is computed for closed fillings (got {dwell})")
check(dwell.get("Reactor 3") == 25.0, "...for every closed vessel, not just one")
check("Reactor 1" not in dwell, "an open filling never contributes to closed dwell time")

check(len(body["qc_trend"]) == 1, "the QC trend has one day's worth of completed checks")
check(body["qc_trend"][0]["avg_hours"] == 1.0, "...averaging to the one round trip's turnaround")

out_at_qc = {o["reactor_name"]: o for o in body["out_at_qc"]}
check(out_at_qc["Reactor 3"]["hours_at_qc"] == 3.0, f"the out-at-QC list carries the live wait time (got {out_at_qc})")

check(len(body["batches"]) == 4, "every filling appears in the full table, not just a subset")
r1 = next(b for b in body["batches"] if b["reactor_name"] == "Reactor 1")
check(r1["open"] is True and r1["hours_in_reactor"] == 10.0,
      f"an open filling still reports hours-so-far (got {r1})")

# --- saving QC is gated behind manage_qc, separately from the read ----------
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
r = client.post(f"/api/batch-history/{id_open}/qc", json={"sent_at": now.isoformat()}, headers=CSRF)
check(r.status_code == 403, f"an operator without manage_qc cannot save QC (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)

# --- set_batch_qc's own validation still applies, ported unchanged ---------
r = client.post(f"/api/batch-history/{id_open}/qc", json={
    "sent_at": now.isoformat(), "result_at": (now - timedelta(hours=1)).isoformat(), "result": "pass",
}, headers=CSRF)
check(r.status_code == 400, f"a result before the sample went out is refused (got {r.status_code}, {r.text[:150]})")

r = client.post(f"/api/batch-history/{id_open}/qc", json={"sent_at": now.isoformat(), "result": "pass"}, headers=CSRF)
check(r.status_code == 400, f"a result with no result time is refused (got {r.status_code}, {r.text[:150]})")

r = client.post(f"/api/batch-history/{id_open}/qc", json={
    "sent_at": (now - timedelta(hours=2)).isoformat(), "result_at": now.isoformat(), "result": "hold",
}, headers=CSRF)
check(r.status_code == 200, f"a well-formed QC entry saves (got {r.status_code}, {r.text[:150]})")

r = client.get("/api/batch-history", params={"days": 30})
r1 = next(b for b in r.json()["batches"] if b["reactor_name"] == "Reactor 1")
check(r1["qc_result"] == "hold" and r1["qc_by"] == "Plant Lead",
      f"the saved QC result and submitter show up on re-read (got {r1})")

r = client.post("/api/batch-history/999999/qc", json={"sent_at": now.isoformat()}, headers=CSRF)
check(r.status_code == 400, f"a nonexistent batch id is refused (got {r.status_code})")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/batch-history")
check(r.status_code == 401, f"batch-history refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API BATCH HISTORY CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API BATCH HISTORY ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
