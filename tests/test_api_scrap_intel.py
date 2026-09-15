"""Quality Ops Canvas, ported from pages/Mgr_Scrap_Intel.py: scrap totals,
output-by-formulation, and downtime-by-reason. Read-only, so the only real
things to prove are the ability gate, the aggregation math, and that each
resin's colour matches what resin_palette.py would compute directly (the
whole point of computing it server-side instead of re-deriving it in React).
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
print("API SCRAP INTEL: Quality Ops Canvas")
print("=" * 66)

# --- gated behind view_manager_cockpit, not a bare role check ---------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/scrap-intel")
check(r.status_code == 403, f"an operator without view_manager_cockpit is refused (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/scrap-intel")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- an empty plant reads as empty, not broken ------------------------------
r = client.get("/api/scrap-intel")
check(r.status_code == 200, f"loads with nothing logged (got {r.status_code})")
body = r.json()
check(body["totals"] == {"empty_scrap": 0, "filled_scrap": 0, "total_scrap": 0},
      f"zero scrap, not an error, with nothing logged (got {body['totals']})")
check(body["by_resin"] == [] and body["downtime_by_reason"] == [],
      "both breakdowns start empty too")

# --- seed real production and downtime, then check the math ----------------
crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=100, scrap_empty=5, scrap_filled=2, log_type="Hourly Bottle Count")
crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V1", "Standard Black V5", "L2",
                    bottles=50, scrap_empty=1, scrap_filled=0, log_type="Hourly Bottle Count")
crud.add_downtime_log("Demo Operator", "New Pump #1", "Shift 1", "Changeover", 20)
crud.add_downtime_log("Demo Operator", "New Pump #1", "Shift 1", "Changeover", 10)
crud.add_downtime_log("Demo Operator", "New Pump #1", "Shift 1", "Break/Shift Change", 15)

r = client.get("/api/scrap-intel")
check(r.status_code == 200, f"loads with real data (got {r.status_code})")
body = r.json()
check(body["totals"] == {"empty_scrap": 6, "filled_scrap": 2, "total_scrap": 8},
      f"scrap totals sum across every log (got {body['totals']})")

by_resin = {row["resin_type"]: row for row in body["by_resin"]}
check(by_resin["Standard Clear V5"]["bottles_filled"] == 100, "output-by-resin sums bottles per formulation")
check(by_resin["Standard Black V5"]["bottles_filled"] == 50, "...for every resin poured, not just one")
check(by_resin["Standard Clear V5"]["color"] == resin_color("Standard Clear V5"),
      "the colour returned matches resin_palette.resin_color exactly")
check(by_resin["Standard Black V5"]["color"] == resin_color("Standard Black V5"),
      "...for both resins, so a chart never disagrees with resin_palette")

by_reason = {row["reason"]: row["duration_min"] for row in body["downtime_by_reason"]}
check(by_reason["Changeover"] == 30, f"downtime sums duration per reason (got {by_reason})")
check(by_reason["Break/Shift Change"] == 15, "...for every reason logged, not just one")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API SCRAP INTEL CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API SCRAP INTEL ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
