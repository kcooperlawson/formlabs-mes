"""Historical Plant Analytics, ported from pages/Mgr_Historical.py: output,
scrap and yield trends over a time horizon, filterable by resin and
operator.
"""
import pathlib
import sys
from datetime import date, timedelta

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
print("API HISTORICAL: Historical Plant Analytics")
print("=" * 66)

# --- gated behind view_manager_cockpit, not a bare role check --------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/historical")
check(r.status_code == 403, f"an operator without view_manager_cockpit is refused (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/historical")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- bad horizon values are rejected, not silently ignored ------------------
r = client.get("/api/historical", params={"horizon": "nonsense"})
check(r.status_code == 400, f"an unsupported horizon is refused (got {r.status_code})")

# --- an empty plant reads as empty, not broken ------------------------------
r = client.get("/api/historical", params={"horizon": "all"})
check(r.status_code == 200, f"loads with nothing logged (got {r.status_code})")
body = r.json()
check(body["totals"] == {"total_poured": 0, "total_packed": 0, "total_scrap": 0, "yield_pct": 100.0},
      f"zero everything (with 100% yield, not a divide-by-zero) with nothing logged (got {body['totals']})")
check(body["filters"] == {"resins": [], "operators": []}, "filter dropdowns start empty too")
check(body["trend"] == [] and body["by_operator"] == [], "both breakdowns start empty too")

# --- seed real production across two operators and two resins --------------
today = date.today()
old_day = today - timedelta(days=60)

crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=100, scrap_empty=5, scrap_filled=0, log_type="Hourly Bottle Count")
crud.add_hourly_log("Sasha", "New Pump #2", "Shift 1", "V1", "Standard Black V5", "L2",
                    bottles=50, scrap_empty=0, scrap_filled=0, log_type="Hourly Bottle Count")
crud.add_hourly_log("Demo Operator", "Pack-Out Station", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=80, scrap_empty=0, scrap_filled=0, log_type="Packing Count")

# Age one row 60 days back, to prove the horizon filter actually filters.
_session = crud.ScopedSession()
old_row = _session.query(crud.ProductionLog).filter_by(operator_name="Sasha").first()
old_row.date = old_day
old_row.timestamp = old_row.timestamp.replace(year=old_day.year, month=old_day.month, day=old_day.day)
_session.commit()
_session.close()

r = client.get("/api/historical", params={"horizon": "all"})
check(r.status_code == 200, f"loads with real data (got {r.status_code})")
body = r.json()
check(body["totals"] == {"total_poured": 150, "total_packed": 80, "total_scrap": 5, "yield_pct": 96.8},
      f"totals sum pouring and packing separately (got {body['totals']})")
check(set(body["filters"]["resins"]) == {"Standard Clear V5", "Standard Black V5"},
      f"resin filter options come from every resin ever logged (got {body['filters']['resins']})")
check(set(body["filters"]["operators"]) == {"Demo Operator", "Sasha"},
      f"operator filter options list everyone who has ever logged (got {body['filters']['operators']})")

by_op = {o["operator"]: o["bottles_filled"] for o in body["by_operator"]}
check(by_op == {"Demo Operator": 100, "Sasha": 50}, f"output-by-operator only counts pouring, not packing (got {by_op})")

# --- the horizon filter actually filters ------------------------------------
r = client.get("/api/historical", params={"horizon": "30d"})
narrow = r.json()
check(narrow["totals"]["total_poured"] == 100, f"a 30-day window drops the 60-day-old row (got {narrow['totals']})")
check("Sasha" not in {o["operator"] for o in narrow["by_operator"]}, "...and Sasha's output disappears with it")

# --- resin and operator filters compose with the horizon -------------------
r = client.get("/api/historical", params={"horizon": "all", "resin": "Standard Black V5"})
resin_filtered = r.json()
check(resin_filtered["totals"]["total_poured"] == 50, f"the resin filter narrows the totals (got {resin_filtered['totals']})")

r = client.get("/api/historical", params={"horizon": "all", "operator": "Demo Operator"})
op_filtered = r.json()
check(op_filtered["totals"]["total_poured"] == 100 and op_filtered["totals"]["total_packed"] == 80,
      f"the operator filter narrows to just that person's rows (got {op_filtered['totals']})")

check(len(body["trend"]) >= 1 and body["trend"][0]["bottles_filled"] > 0,
      f"the trend series carries real daily totals (got {body['trend']})")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/historical")
check(r.status_code == 401, f"historical refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API HISTORICAL CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API HISTORICAL ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
