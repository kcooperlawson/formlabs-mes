"""Plant Command wall display, ported from pages/Tv_Dashboard.py: today's
pace against target, top pourers, packing breakdown, active work orders.

Pace/rate figures depend on real wall-clock time (elapsed hours since a
shift start), same as Analytics Hub's live ticker - those get range/type
checks here, not exact values. Day-wide totals (poured/packed/WIP) and the
relative ranking of seeded operators don't depend on the clock and are
checked exactly.
"""
import pathlib
import sys
from datetime import date, datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402

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
print("API TV: the Plant Command wall display")
print("=" * 66)

# --- access control ----------------------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/tv/overview")
check(r.status_code == 403, f"an operator is refused the TV dashboard (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/tv/overview")
check(r.status_code == 401, f"an anonymous request is refused too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin account can log in (got {r.status_code})")

# --- an empty plant reads as empty, not broken ------------------------------
r = client.get("/api/tv/overview")
check(r.status_code == 200, f"loads with nothing logged (got {r.status_code})")
body = r.json()
check(body["health"]["state"] == "no-record", f"the health band reads 'nothing logged yet' (got {body['health']})")
check(body["total_poured"] == 0 and body["total_packed"] == 0 and body["unpacked_wip"] == 0,
      f"every total is zero with nothing logged (got poured={body['total_poured']} packed={body['total_packed']})")
check(body["top_pourers"] == [] and body["packing_breakdown"] == [],
      "the leaderboard and packing breakdown both start empty")

# --- pin Shift 1 to cover the whole day, so which shift is "active" doesn't
# depend on what time this test happens to run -----------------------------
client.put("/api/admin/settings", json={
    "shift_1_start": "00:00", "shift_1_hours": 24.0, "shift_1_break_mins": 0,
    "shift_2_start": "23:58", "shift_2_hours": 0.03, "shift_2_break_mins": 0,
    "shift_count": 2, "target_lph": 400.0, "yield_target_pct": 99.0,
    "enable_packing": True, "enable_bulk_pour": False, "enable_device_gateway": False,
    "operating_days": [0, 1, 2, 3, 4, 5, 6], "use_work_orders": True,
    "pump_form_url": "", "pump_form_label": "",
}, headers=CSRF)

today = date.today()
now = datetime.utcnow()


def seed_pour(operator, units, log_type="Hourly Bottle Count", resin="Standard Clear V5", lot="L1"):
    crud.add_hourly_log(operator, "New Pump #1", "Shift 1", "V2", resin, lot, bottles=units,
                        scrap_empty=0, scrap_filled=0, log_type=log_type)
    session = crud.ScopedSession()
    row = session.query(crud.ProductionLog).order_by(crud.ProductionLog.id.desc()).first()
    row.date = today
    row.timestamp = now
    session.commit()
    session.close()


# Demo Operator clearly outpaces Sasha - both logged at the same instant, so
# their op_hours denominator is identical and only the liters decide rank.
seed_pour("Demo Operator", 300)
seed_pour("Sasha", 100)
seed_pour("Demo Operator", 250, log_type="Packing Count", resin="Standard Clear V5", lot="L1")
seed_pour("Sasha", 100, log_type="Packing Count", resin="Standard Black V5", lot="L2")

r = client.get("/api/tv/overview")
check(r.status_code == 200, f"loads with real data (got {r.status_code})")
body = r.json()

check(body["total_poured"] == 400, f"total poured sums both operators (got {body['total_poured']})")
check(body["total_packed"] == 350, f"total packed sums both packing rows (got {body['total_packed']})")
check(body["unpacked_wip"] == 50, f"WIP is poured minus packed, day-wide regardless of shift toggle (got {body['unpacked_wip']})")

pourers = body["top_pourers"]
check(len(pourers) == 2, f"both operators who poured today show up (got {pourers})")
check(pourers[0]["operator"] == "Demo Operator" and pourers[1]["operator"] == "Sasha",
      f"Demo Operator (300L) outranks Sasha (100L) (got {pourers})")
check(pourers[0]["rate_lph"] > pourers[1]["rate_lph"], "...and the rate figures agree with the ranking")

specs = crud.get_all_resin_specs_df("ALL")
clear_skid = float(specs[specs["resin_name"] == "Standard Clear V5"].iloc[0]["units_per_skid"] or 500)
black_skid = float(specs[specs["resin_name"] == "Standard Black V5"].iloc[0]["units_per_skid"] or 500)

pack = {row["resin"]: row for row in body["packing_breakdown"]}
check(set(pack) == {"Standard Clear V5", "Standard Black V5"}, f"both packed resins show up (got {list(pack)})")
check(pack["Standard Clear V5"]["units"] == 250 and pack["Standard Clear V5"]["lot_number"] == "L1",
      f"the packing row carries the right units and lot (got {pack['Standard Clear V5']})")
check(abs(pack["Standard Clear V5"]["skids"] - round(250 / clear_skid, 1)) < 0.05,
      f"skids are worked out from the resin's own skid size, not a hardcoded 500 (got {pack['Standard Clear V5']['skids']})")
check(all(row["color"] for row in body["packing_breakdown"]), "every packed resin carries a resolved colour")

# --- pace/rate figures are time-of-day dependent: sanity-check, don't pin --
check(body["current_output_l"] > 0, "some volume has been poured today")
check(isinstance(body["current_run_rate_lph"], (int, float)) and body["current_run_rate_lph"] >= 0,
      "the current run rate is a real, non-negative number")
check(0.0 <= body["build_pct"] <= 100.0 or body["shift_target_l"] == 0,
      f"build percentage is a sane fraction whenever there's a shift target (got {body['build_pct']})")
check(body["active_shift"] == "Shift 1", f"Shift 1 covers the whole day per the pinned settings (got {body['active_shift']})")
check(body["health"]["state"] in ("flowing", "idle", "quiet"), f"health reflects a log that just landed (got {body['health']})")

r = client.get("/api/tv/overview?mode=daily")
check(r.status_code == 200, f"daily mode loads too (got {r.status_code})")
daily = r.json()
check(daily["active_shift"] == "ALL SHIFTS (DAILY TOTAL)", f"daily mode labels itself correctly (got {daily['active_shift']})")
check(daily["total_poured"] == 400 and daily["unpacked_wip"] == 50,
      "day-wide totals are identical between auto and daily mode")

# --- work orders: only the ones actually running show up, and only when the
# plant isn't in simple/logging mode -----------------------------------------
crud.add_reactor("TV Test Reactor", 5000)
crud.create_assigned_run("TV Test Reactor", 5000, "Standard Clear V5", "V2", 1000,
                         "Demo Operator", "New Pump #1", "L1", "", status="Active")
crud.create_assigned_run("TV Test Reactor", 5000, "Standard Black V5", "V2", 500,
                         "Sasha", "New Pump #1", "L2", "", status="Done")

r = client.get("/api/tv/overview")
body = r.json()
check(body["show_runs_card"] is True, f"the plant is in execution mode, so the work-orders card shows (got {body['show_runs_card']})")
orders = body["work_orders"]
check(len(orders) == 1, f"only the Active run appears, not the Done one (got {orders})")
check(orders[0]["resin_type"] == "Standard Clear V5" and orders[0]["target_units"] == 1000,
      f"the active run's numbers came through (got {orders[0]})")
check(orders[0]["progress_pct"] >= 0.0, "progress is a real percentage")

# --- switching back to logging mode hides the work-orders card -------------
client.put("/api/admin/settings", json={
    "shift_1_start": "00:00", "shift_1_hours": 24.0, "shift_1_break_mins": 0,
    "shift_2_start": "23:58", "shift_2_hours": 0.03, "shift_2_break_mins": 0,
    "shift_count": 2, "target_lph": 400.0, "yield_target_pct": 99.0,
    "enable_packing": True, "enable_bulk_pour": False, "enable_device_gateway": False,
    "operating_days": [0, 1, 2, 3, 4, 5, 6], "use_work_orders": False,
    "pump_form_url": "", "pump_form_label": "",
}, headers=CSRF)
body = client.get("/api/tv/overview").json()
check(body["show_runs_card"] is False, f"logging mode hides the work-orders card (got {body['show_runs_card']})")
check(body["work_orders"] == [], "...and the router doesn't even bother computing it")

client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/tv/overview")
check(r.status_code == 401, f"the TV dashboard refuses an anonymous request too (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API TV CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API TV ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
