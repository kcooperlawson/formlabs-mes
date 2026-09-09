"""The expected output is worked out from the pumps that were actually on.

Everything here is about the one property that matters: the target must not be
able to move itself to meet the output. A day with one pourer expects one
pump's worth, a day with three expects three, and a pump that was certified
and then went quiet is still counted against the shift.
"""
import pathlib
import sys
from datetime import datetime, date, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import _boot  # noqa: E402
_boot.boot(fresh=True, db_name="formlabs_pace")

import pace  # noqa: E402
from crud import (add_pump_station, add_resin_spec, add_hourly_log,  # noqa: E402
                  submit_daily_checklist, add_downtime_log, get_all_pumps_df)
from shift_clock import PLANT_TZ  # noqa: E402
from db_core import ScopedSession  # noqa: E402
from models import DailyChecklist, ProductionLog  # noqa: E402
from datetime import timezone as _tz


def certify_at(station, shift, when):
    """A checklist row stamped when we say, not when the test happens to run.

    submit_daily_checklist writes utcnow, which is correct on the floor and
    useless here: a simulated shift window would always be certified after it
    ended. Rows are stored naive UTC, so that is what goes back in.
    """
    submit_daily_checklist(f"Op {station}", shift, station)
    naive = when.astimezone(_tz.utc).replace(tzinfo=None)
    session = ScopedSession()
    try:
        for r in session.query(DailyChecklist).filter(
                DailyChecklist.pump_station == station,
                DailyChecklist.shift == shift).all():
            r.timestamp = naive
        session.commit()
    finally:
        session.close()


def backdate_logs(lot, when):
    """Put a batch of logs on a real earlier shift so measured_rates has
    more than one day to take a median over."""
    session = ScopedSession()
    try:
        rows = session.query(ProductionLog).filter(
            ProductionLog.lot_number == lot).all()
        for i, r in enumerate(rows):
            r.date = when.date()
            r.timestamp = (when + timedelta(hours=i)).astimezone(
                _tz.utc).replace(tzinfo=None)
        session.commit()
    finally:
        session.close()

FAILS, CHECKS = [], 0


def check(label, got, exp, tol=0.51):
    global CHECKS
    CHECKS += 1
    ok = (abs(float(got) - float(exp)) <= tol
          if isinstance(exp, (int, float)) and not isinstance(exp, bool)
          else got == exp)
    if not ok:
        FAILS.append(f"{label}: got {got!r}, expected {exp!r}")
    print(("  ok   " if ok else "  FAIL ") + label)


SETTINGS = {
    "target_lph": 400.0,
    "shift_1_start": "06:00", "shift_1_hours": 8.0, "shift_1_break_mins": 0.0,
    "shift_2_start": "14:00", "shift_2_hours": 8.0, "shift_2_break_mins": 0.0,
}

TODAY = date.today()
START = datetime.combine(TODAY, datetime.min.time(), tzinfo=PLANT_TZ).replace(hour=6)
FOUR_HOURS_IN = START + timedelta(hours=4)

add_pump_station("Old Pump")
add_pump_station("New Pump")
add_pump_station("Idle Pump")
add_resin_spec("V2", "SKU-P1", "CP1", "Pace Resin V1",
               1110.0, 1100.0, 1115.0, "1100-1115", 1.0, 24)

_pumps = {r["station_name"]: int(r["id"]) for _, r in get_all_pumps_df().iterrows()}

# --- nothing certified: exactly what the plant did before ------------------
r = pace.expected_for_shift(SETTINGS, "Shift 1", START, now=FOUR_HOURS_IN)
check("with nothing certified it falls back to the plant figure", r["derived"], False)
check("and that is the old arithmetic, 400 x 4", r["expected_l"], 1600.0)

# --- the rate goes on the pump ---------------------------------------------
check("a pump with no rate uses the plant figure",
      pace.pump_rates(400.0)["Old Pump"], 400.0)
check("setting one takes", pace.set_pump_rate(_pumps["Old Pump"], 250.0), True)
pace.set_pump_rate(_pumps["New Pump"], 500.0)
check("the old pump expects less", pace.pump_rates(400.0)["Old Pump"], 250.0)
check("the new one expects more", pace.pump_rates(400.0)["New Pump"], 500.0)
check("and an unset pump still falls back",
      pace.pump_rates(400.0)["Idle Pump"], 400.0)

# --- one pourer expects one pump's worth -----------------------------------
certify_at("Old Pump", "Shift 1", START)
r = pace.expected_for_shift(SETTINGS, "Shift 1", START, now=FOUR_HOURS_IN)
check("one certified pump is one pump's worth", r["derived"], True)
check("250 an hour for four hours", r["expected_l"], 1000.0)
check("the live rate is that pump's rate", r["rate_lph"], 250.0)
check("the whole shift is eight hours of it", r["shift_target_l"], 2000.0)
check("and it names the station", [s["station"] for s in r["stations"]], ["Old Pump"])

# --- three pourers expect three pumps --------------------------------------
certify_at("New Pump", "Shift 1", START)
certify_at("Idle Pump", "Shift 1", START)
r = pace.expected_for_shift(SETTINGS, "Shift 1", START, now=FOUR_HOURS_IN)
check("three pumps add up", r["rate_lph"], 1150.0)
check("and so does what they should have poured", r["expected_l"], 4600.0)

# --- a pump that was certified and poured nothing still counts -------------
# This is the whole point. If the expectation came off the logs, a station
# that poured nothing would expect nothing and the plant could never be
# behind. Nothing has been logged at all yet and the target is 4,600 L.
check("a silent certified pump is still expected to have poured",
      r["expected_l"] > 0 and len(r["stations"]) == 3, True)

# --- downtime comes off ----------------------------------------------------
add_downtime_log("Op Two", "New Pump", "Shift 1", "Changeover", 60)
r = pace.expected_for_shift(SETTINGS, "Shift 1", START, now=FOUR_HOURS_IN)
check("an hour down takes 500 L off the expectation", r["expected_l"], 4100.0)
check("and off the whole shift target too", r["shift_target_l"],
      250 * 8 + 500 * 7 + 400 * 8)

# --- a late start is not charged for hours nobody was there ----------------
# Op One certified at the top of the shift in this test, so the only way to
# exercise the clamp is a shift that started before the checklist did.
certify_at("Idle Pump", "Shift 1", START + timedelta(hours=3))
r_late = pace.expected_for_shift(SETTINGS, "Shift 1", START, now=FOUR_HOURS_IN)
# Idle Pump now only owns the last hour of the four, so 400 instead of 1,600.
check("a pump certified late is not charged for the hours nobody was there",
      r_late["expected_l"], 4100.0 - 1200.0)

# --- the measured rate, for reviewing a target instead of inventing one ----
for day_back in range(4):
    d = START - timedelta(days=day_back)
    for _hour in range(3):
        add_hourly_log("Op One", "Old Pump", "Shift 1", "V2", "Pace Resin V1",
                       f"L-PACE{day_back}", 200, 0, 0)
    backdate_logs(f"L-PACE{day_back}", d)

m = pace.measured_rates()
check("a pump with no history at all is left out",
      "New Pump" in m, False)
check("one with four shifts behind it is measured", m["Old Pump"]["samples"], 4)
# 3 logs an hour apart is a two hour span, counted as three hours the same way
# the wall counts an operator. 600 L over 3 h.
check("and the median is what it actually ran at",
      m["Old Pump"]["median_lph"], 200.0, tol=1.0)

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} PACE CHECKS FAILED:\n" + "\n".join("  " + f for f in FAILS))
else:
    print(f"ALL {CHECKS} PACE ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
