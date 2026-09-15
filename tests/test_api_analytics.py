"""Nexus Analytics, ported from pages/Analytics_Hub.py: the rolling 7-day
KPI/trend/heatmap/fill-weight dashboard.
"""
import pathlib
import sys
from datetime import date, datetime, timedelta

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
print("API ANALYTICS: Nexus Analytics rolling 7-day dashboard")
print("=" * 66)

# --- gated behind view_analytics ---------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/analytics/overview")
check(r.status_code == 403, f"an operator without view_analytics is refused (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/analytics/overview")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- an empty plant reads as empty, not broken ------------------------------
r = client.get("/api/analytics/overview")
check(r.status_code == 200, f"loads with nothing logged (got {r.status_code})")
body = r.json()
check(body["kpis"] == {"total_poured_7d": 0, "pour_delta_pct": 0.0, "yield_7d": 100.0,
                       "yield_target_pct": 99.0, "total_scrap_7d": 0, "downtime_hours_7d": 0.0,
                       "downtime_minutes_7d": 0},
      f"zero everything, 100% yield not a divide-by-zero, with nothing logged (got {body['kpis']})")
check(body["velocity_trend"] == [] and body["formulation_output"] == [] and body["downtime_pareto"] == [],
      "every breakdown starts empty too")
check(body["fill_weight"]["has_readings"] is False, "fill weight panel reads as 'nothing weighed yet', not broken")
check(isinstance(body["live_ticker"]["expected_now_l"], (int, float)), "the live ticker still returns real numbers with nothing logged")

# --- seed production spread across the current and previous 7-day window ---
today = date.today()
this_week = today - timedelta(days=2)
last_week = today - timedelta(days=9)


def seed_on(day, operator, pump, resin, bottles, scrap, weight=None):
    crud.add_hourly_log(operator, pump, "Shift 1", "V2", resin, "L1", bottles=bottles,
                        scrap_empty=scrap, scrap_filled=0, log_type="Hourly Bottle Count", weight=weight)
    session = crud.ScopedSession()
    row = session.query(crud.ProductionLog).order_by(crud.ProductionLog.id.desc()).first()
    row.date = day
    row.timestamp = datetime.combine(day, datetime.min.time()) + timedelta(hours=10)
    session.commit()
    session.close()


seed_on(this_week, "Demo Operator", "New Pump #1", "Standard Clear V5", 100, 5)
seed_on(this_week, "Sasha", "New Pump #2", "Standard Black V5", 50, 0)
seed_on(last_week, "Demo Operator", "New Pump #1", "Standard Clear V5", 40, 0)
crud.add_downtime_log("Demo Operator", "New Pump #1", "Shift 1", "Changeover", 20)

r = client.get("/api/analytics/overview")
check(r.status_code == 200, f"loads with real data (got {r.status_code})")
body = r.json()
check(body["kpis"]["total_poured_7d"] == 150, f"the KPI sums only the trailing 7 days (got {body['kpis']})")
check(body["kpis"]["pour_delta_pct"] == round((150 - 40) / 40 * 100, 1),
      f"the week-over-week delta compares against the PRIOR 7-day window, not all-time (got {body['kpis']['pour_delta_pct']})")
check(body["kpis"]["total_scrap_7d"] == 5, "scrap sums the trailing week too")
check(body["kpis"]["downtime_minutes_7d"] == 20, "downtime is included in the KPI row")

resins = {r["resin"]: r["units"] for r in body["formulation_output"]}
check(resins == {"Standard Clear V5": 100, "Standard Black V5": 50},
      f"the formulation donut only covers the trailing 7 days (the 40 units from last week are excluded) (got {resins})")
check(all(r["color"] for r in body["formulation_output"]), "every resin slice carries a resolved colour")

reasons = {d["reason"]: d["minutes"] for d in body["downtime_pareto"]}
check(reasons == {"Changeover": 20.0}, f"the downtime pareto matches what was logged (got {reasons})")

ops = {c["operator"] for c in body["operator_matrix"]}
check(ops == {"Demo Operator", "Sasha"}, f"the operator heatmap covers everyone who logged in the 14-day fetch (got {ops})")
check(set(body["top_operators"]) == {"Demo Operator", "Sasha"}, "...and both show up in the top-operators list")

# --- fill weight give-away ------------------------------------------------
seed_on(today, "Demo Operator", "New Pump #1", "Standard Clear V5", 20, 0,
       weight={"measured": 1114.0, "deviation": 4.0, "status": "over"})
seed_on(today, "Sasha", "New Pump #2", "Standard Black V5", 20, 0,
       weight={"measured": 1108.0, "deviation": -2.0, "status": "in"})

r = client.get("/api/analytics/overview")
fw = r.json()["fill_weight"]
check(fw["has_readings"] is True and fw["samples"] == 2, f"both weighed readings are picked up (got {fw})")
check(fw["mean_deviation"] == 1.0, f"the mean deviation is unit-weighted across both readings (got {fw['mean_deviation']})")
check(len(fw["scatter"]) == 2, "every reading appears in the scatter data")
by_pump = {p["pump_station"]: p for p in fw["by_pump"]}
check(by_pump["New Pump #1"]["mean_deviation"] == 4.0 and by_pump["New Pump #2"]["mean_deviation"] == -2.0,
      f"per-pump means are computed separately, not blended together (got {by_pump})")
check(fw["worst_pump_note"] is not None and "New Pump #1" in fw["worst_pump_note"],
      f"the worst-running-heavy pump gets an actionable caption (got {fw['worst_pump_note']})")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/analytics/overview")
check(r.status_code == 401, f"analytics refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API ANALYTICS CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API ANALYTICS ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
