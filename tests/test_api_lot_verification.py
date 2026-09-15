"""Cartridge Lot Verification, ported from pages/Mgr_Lot_Verification.py -
the manager-side review of the lot gate pouring_tab.py/api/routers/pouring.py
already enforce. Checks the window filter, the summary math, the flagged
list, and the two coverage breakdowns.
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
from resin_palette import resin_color  # noqa: E402

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
print("API LOT VERIFICATION: Cartridge Lot Verification review")
print("=" * 66)

# --- gated behind view_manager_cockpit, not a bare role check --------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/lot-verification")
check(r.status_code == 403, f"an operator without view_manager_cockpit is refused (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/lot-verification")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- bad window values are rejected, not silently ignored -------------------
r = client.get("/api/lot-verification", params={"days": 3})
check(r.status_code == 400, f"an unsupported window is refused (got {r.status_code})")

# --- an empty window reads as empty, not broken -----------------------------
r = client.get("/api/lot-verification", params={"days": 30})
check(r.status_code == 200, f"loads with nothing logged (got {r.status_code})")
body = r.json()
check(body["totals"] == {"checks_logged": 0, "full_checks": 0, "pct_full": 0, "flagged": 0,
                         "cartridges_pulled": 0, "flag_rate": 0},
      f"zero everything, not an error, with nothing logged (got {body['totals']})")
check(body["checks"] == [] and body["by_operator"] == [] and body["by_station"] == [],
      "every breakdown starts empty too")

# --- seed a realistic mix of checks -----------------------------------------
crud.add_lot_verification({
    "operator_name": "Demo Operator", "pump_station": "New Pump #1", "cartridge_type": "V2",
    "resin_type": "Standard Clear V5", "expected_lot": "L1", "entered_lot": "L1",
    "result": "verified", "check_level": "full",
})
crud.add_lot_verification({
    "operator_name": "Demo Operator", "pump_station": "New Pump #1", "cartridge_type": "V2",
    "resin_type": "Standard Clear V5", "expected_lot": "L1", "entered_lot": "L1",
    "result": "verified", "check_level": "fast",
})
crud.add_lot_verification({
    "operator_name": "Sasha", "pump_station": "New Pump #2", "cartridge_type": "V1",
    "resin_type": "Standard Black V5", "expected_lot": "L2", "entered_lot": "L9",
    "result": "mismatch", "check_level": "full", "reason": "Ran low, grabbed the nearest box.",
})
crud.add_lot_verification({
    "operator_name": "Sasha", "pump_station": "New Pump #2", "cartridge_type": "V1",
    "resin_type": "Standard Black V5", "expected_lot": "L2", "entered_lot": "L9",
    "result": "rejected", "check_level": "full", "reason": "Wrong lot, pulled it before pouring.",
})

r = client.get("/api/lot-verification", params={"days": 30})
check(r.status_code == 200, f"loads with real data (got {r.status_code})")
body = r.json()
check(body["totals"] == {"checks_logged": 4, "full_checks": 3, "pct_full": 75.0, "flagged": 2,
                         "cartridges_pulled": 1, "flag_rate": 50.0},
      f"summary math matches (got {body['totals']})")

checks = body["checks"]
check(len(checks) == 4, "every check comes back, not just the flagged ones")
by_result = {c["result"]: c for c in checks if c["result"] in ("mismatch", "rejected")}
check(by_result["mismatch"]["resin_color"] == resin_color("Standard Black V5"),
      "each check carries its resin's colour, computed the same way everywhere else")
check(by_result["mismatch"]["expected_lot"] == "L2" and by_result["mismatch"]["entered_lot"] == "L9",
      "a mismatch keeps both the expected and the entered lot")
check(by_result["rejected"]["production_log_id"] is None,
      "a rejected cartridge carries no production log - the pull is the point, not a miss")

by_op = {r["operator_name"]: r for r in body["by_operator"]}
check(by_op["Demo Operator"] == {"operator_name": "Demo Operator", "checks": 2, "full": 1, "fast": 1,
                                 "flags": 0, "pct_full": 50.0},
      f"per-operator coverage breaks down full vs fast vs flagged (got {by_op['Demo Operator']})")
check(by_op["Sasha"]["flags"] == 2, "...and Sasha's two flagged checks show up on her row")

by_station = {r["pump_station"]: r for r in body["by_station"]}
check(by_station["New Pump #2"]["flags"] == 2, "per-station coverage sums flags the same way")
check(by_station["New Pump #1"]["flags"] == 0, "...and a clean station shows zero")

# --- the window filter actually filters ------------------------------------
import crud as _crud  # noqa: E402
from datetime import datetime, timedelta  # noqa: E402
old_session = _crud.ScopedSession()
try:
    old_row = old_session.query(_crud.LotVerification).filter_by(operator_name="Sasha", result="mismatch").first()
    old_row.timestamp = datetime.utcnow() - timedelta(days=60)
    old_session.commit()
finally:
    old_session.close()

r = client.get("/api/lot-verification", params={"days": 7})
check(r.status_code == 200, f"a narrow window loads fine (got {r.status_code})")
narrow = r.json()
check(narrow["totals"]["checks_logged"] == 3, f"the 60-day-old row drops out of a 7-day window (got {narrow['totals']})")

r = client.get("/api/lot-verification", params={"days": 90})
wide = r.json()
check(wide["totals"]["checks_logged"] == 4, "...but a 90-day window still includes it")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/lot-verification")
check(r.status_code == 401, f"lot-verification refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API LOT VERIFICATION CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API LOT VERIFICATION ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
