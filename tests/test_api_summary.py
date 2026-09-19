"""My Shift Summary - a read-only, on-demand personal breakdown, ported
from pages/operator_form/summary_tab.py. Three states worth telling apart:
nothing logged at all today, logs of the WRONG type only (e.g. a packer's
downtime-only day), and a real day with output to summarize.
"""
import pathlib
import sys
from datetime import date

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import api.main  # noqa: E402
import crud  # noqa: E402


def _ordinal(n):
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"

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

# --- litres: Pigment is 0.124 L/unit (crud.CONTAINER_LITRES) -----------------
check(abs(body["litres"] - 150 * 0.124) < 0.01, f"litres follow the cartridge format, not just a unit count (got {body['litres']})")
by_resin_litres = {p["resin"]: p["litres"] for p in body["by_resin"]}
check(abs(by_resin_litres["Standard Clear V5"] - 100 * 0.124) < 0.01,
      f"each resin's own litres reflect its own units (got {by_resin_litres})")
check(abs(by_resin_litres["Standard Black V5"] - 50 * 0.124) < 0.01,
      f"each resin's own litres reflect its own units (got {by_resin_litres})")
check({p["cartridge_type"] for p in body["by_cartridge"]} == {"Pigment"},
      f"both pours were Pigment format, so the cartridge breakdown has one entry (got {body['by_cartridge']})")
by_cartridge_units = {p["cartridge_type"]: p["units"] for p in body["by_cartridge"]}
check(by_cartridge_units["Pigment"] == 150, f"the cartridge breakdown's units sum across both pours (got {by_cartridge_units})")

# --- the login recap: same day's pours, rolled up for the whole month -------
r = client.get("/api/summary/monthly")
check(r.status_code == 200, f"monthly recap loads (got {r.status_code})")
body = r.json()
today_ordinal = _ordinal(date.today().day)
check(body["has_data"] is True, "today's pours count as this month's data")
check(body["units"] == 150, f"monthly units match today's, since today is the only day so far (got {body['units']})")
check(body["best_day_ordinal"] == today_ordinal,
      f"the only day logged is naturally the best one (got {body['best_day_ordinal']!r}, wanted {today_ordinal!r})")
check(body["best_day_units"] == 150, f"best day's units match the day total (got {body['best_day_units']})")
check(body["mismatches"] == 0, "no flagged pours yet, so the recap says so")

# A mismatch this month should show up in the count, attributed by
# operator_id rather than the name string, the same way the rest of this
# operator's data is scoped.
crud.add_lot_verification({
    "operator_name": "Demo Operator", "pump_station": "New Pump #1", "cartridge_type": "V2",
    "resin_type": "Standard Clear V5", "expected_lot": "L1", "entered_lot": "L9",
    "result": "mismatch", "check_level": "full", "reason": "Grabbed the nearest box.",
})
r = client.get("/api/summary/monthly")
check(r.json()["mismatches"] == 1, f"the mismatch is counted (got {r.json()['mismatches']})")

# --- a packer only sees Packing Count, not another role's pours -------------
r = client.post("/api/auth/login", json={"username": "sasha", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, "a second operator can log in")
r = client.get("/api/summary/today")
check(r.json()["has_logs_today"] is False, "a different operator's summary is scoped to their own logs only")
r = client.get("/api/summary/monthly")
body = r.json()
check(body["has_data"] is False, "a different operator's recap is scoped to their own logs too")
check(body["mismatches"] == 0, "and does not pick up the first operator's flagged pour")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/summary/today")
check(r.status_code == 401, f"summary refuses an anonymous request (got {r.status_code})")
r = client.get("/api/summary/monthly")
check(r.status_code == 401, f"the monthly recap refuses an anonymous request too (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API SUMMARY CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API SUMMARY ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
