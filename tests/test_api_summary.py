"""My Shift Summary - a read-only, on-demand personal breakdown, ported
from pages/operator_form/summary_tab.py. Three states worth telling apart:
nothing logged at all today, logs of the WRONG type only (e.g. a packer's
downtime-only day), and a real day with output to summarize.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

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
print("API SUMMARY: My Shift Summary")
print("=" * 66)

r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")

# --- nothing logged today at all --------------------------------------------
r = client.get("/api/summary/today")
check(r.status_code == 200, f"summary loads with nothing logged (got {r.status_code})")
body = r.json()
check(body["has_logs_today"] is False, "a clean day says so")
check(body["units"] == 0 and body["logs_submitted"] == 0, "everything reads zero, not an error")

# --- a downtime-only day: logged something, but nothing this tab counts ----
client.post("/api/downtime/submit", json={"station": "New Pump #1", "reason": "Break/Shift Change",
                                          "duration_min": 15}, headers=CSRF)
r = client.get("/api/summary/today")
body = r.json()
check(body["has_logs_today"] is False,
      "downtime isn't a ProductionLog at all, so the day still reads as nothing logged")

# --- a real pouring day ------------------------------------------------
client.post("/api/pouring/submit", data={
    "station": "New Pump #1", "cartridge_type": "Pigment", "resin": "Standard Clear V5",
    "entered_lot": "L1", "bottles_filled": "100",
}, headers=CSRF)
client.post("/api/pouring/submit", data={
    "station": "New Pump #1", "cartridge_type": "Pigment", "resin": "Standard Black V5",
    "entered_lot": "L2", "bottles_filled": "50", "scrap_empty": "5",
}, headers=CSRF)

r = client.get("/api/summary/today")
check(r.status_code == 200, f"summary loads with real output (got {r.status_code})")
body = r.json()
check(body["has_logs_today"] is True, "a real day says so")
check(body["has_output_logs"] is True, "...and that the output specifically is real")
check(body["units"] == 150, f"units sum across both logs (got {body['units']})")
check(body["scrap"] == 5, f"scrap sums too (got {body['scrap']})")
check(abs(body["yield_pct"] - (150 / 155 * 100)) < 0.1, f"yield is units/(units+scrap) (got {body['yield_pct']})")
check(body["logs_submitted"] == 2, f"two logs submitted today (got {body['logs_submitted']})")
check({p["resin"] for p in body["by_resin"]} == {"Standard Clear V5", "Standard Black V5"},
      f"both resins show up in the breakdown (got {body['by_resin']})")
check(len(body["hourly_timeline"]) >= 1, "at least one hour bucket exists")

# --- a packer only sees Packing Count, not another role's pours -------------
r = client.post("/api/auth/login", json={"username": "sasha", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, "a second operator can log in")
r = client.get("/api/summary/today")
check(r.json()["has_logs_today"] is False, "a different operator's summary is scoped to their own logs only")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/summary/today")
check(r.status_code == 401, f"summary refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API SUMMARY CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API SUMMARY ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
