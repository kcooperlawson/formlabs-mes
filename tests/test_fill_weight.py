"""Fill-weight capture: the arithmetic, the write path, and the two rules.

The two rules are the whole design, and both are easy to break later without
noticing, so they are asserted against the real rendered page rather than
described in a comment:

  1. **It never blocks.** A wrong lot is a defect and the lot gate stops the
     line for it. A heavy cartridge is information. If a missing or an
     out-of-band weight could ever disable the submit button, operators would
     stop weighing and start typing, and the column would fill with numbers
     nobody measured.

  2. **It is never pre-filled.** The run card used to print the lot the gate
     was hiding, which made the whole check decorative. A weight box that
     already contains the target does exactly the same thing to this one.

Run after test_workflow.py - it reads the shift that test builds.
"""
import os
import sys
import warnings

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _boot import boot, ROOT  # noqa: E402

boot(fresh=False)

import sqlalchemy as sa  # noqa: E402
import fill_weight as fw  # noqa: E402

CHECKS = 0


def check(cond, label):
    global CHECKS
    assert cond, f"FAILED: {label}"
    CHECKS += 1


def section(title):
    print("\n" + "=" * 66)
    print(title)
    print("=" * 66)


SPEC = {"target": 1110.0, "lo": 1100.0, "hi": 1115.0}

# ------------------------------------------------------------- arithmetic --
section("1. JUDGING ONE READING")
v = fw.judge(1113, SPEC)
check(v["status"] == fw.IN, "1113 is inside 1100-1115")
check(v["deviation"] == 3.0, "deviation is measured minus target")
check(v["pct_of_fill"] == round(3 / 1110 * 100, 3), "deviation as a share of the fill")
check(fw.judge(1110, SPEC)["deviation"] == 0.0, "on target is zero, not None")
check(fw.judge(1100, SPEC)["status"] == fw.IN, "the low limit itself is in band")
check(fw.judge(1115, SPEC)["status"] == fw.IN, "the high limit itself is in band")
check(fw.judge(1099.9, SPEC)["status"] == fw.UNDER, "below the low limit is under")
check(fw.judge(1115.1, SPEC)["status"] == fw.OVER, "above the high limit is over")
check(fw.judge(1105, SPEC)["deviation"] < 0, "under target is a negative deviation")
print("  in / under / over and the deviation sign all correct")

# The window is lopsided - 10 g under, 5 g over - which is the whole reason
# this feature exists, so pin it rather than assume it.
check(SPEC["target"] - SPEC["lo"] > SPEC["hi"] - SPEC["target"],
      "the tolerance window really is asymmetric")
check(fw.judge(1102, SPEC)["status"] == fw.IN and fw.judge(1117, SPEC)["status"] == fw.OVER,
      "7 g under is fine while 7 g over is not")
print("  running high leaves the window sooner than running low")

section("2. NOTHING TO JUDGE IS NOT AN ERROR")
for bad in (None, "", "  ", "abc", float("nan"), 0, -5, 1e9):
    check(fw.judge(bad, SPEC) is None, f"unusable reading {bad!r} returns None")
check(fw.judge(1110, None) is None, "no spec means no verdict")
check(fw.judge(1110, {}) is None, "an empty spec means no verdict")
check(fw.judge(1110, {"target": 1110, "lo": None, "hi": None})["status"] is None,
      "a target with no window records the reading but judges nothing")
print("  every unusable input degrades to None rather than raising")

section("3. READING A SPEC OFF A RESIN ROW")
check(fw.spec_from_row({"actual_spec_g": 1110, "min_weight_g": 1100, "max_weight_g": 1115})
      == SPEC, "a normal row")
check(fw.spec_from_row(None) is None, "no row")
check(fw.spec_from_row({}) is None, "row with no numbers")
check(fw.spec_from_row({"actual_spec_g": 0, "min_weight_g": 1, "max_weight_g": 2}) is None,
      "a zero target is not a spec")
check(fw.spec_from_row({"actual_spec_g": 1110, "min_weight_g": 1200, "max_weight_g": 1100}) is None,
      "an incoherent window is refused rather than judged against")
print("  a resin with no usable spec yields None, and the form keeps working")

section("4. WHAT THE OPERATOR IS TOLD")
icon, msg = fw.describe(fw.judge(1113, SPEC))
check("In band" in msg and "3.0 g over" in msg, "in-band reading names the gap")
_, over = fw.describe(fw.judge(1120, SPEC))
check("Over the high limit" in over and "lead" in over, "out of band says what to do")
_, under = fw.describe(fw.judge(1090, SPEC))
check("Under the low limit" in under, "under is distinguished from over")
_, exact = fw.describe(fw.judge(1110, SPEC))
check("exactly on target" in exact, "on target reads as on target, not '0.0 g over'")
check(fw.describe(None) == ("", ""), "nothing to say about no reading")
print("  feedback is specific enough to be worth reading")

section("5. GIVE-AWAY, WEIGHTED BY THE UNITS EACH READING STANDS FOR")
# One weight an hour samples that hour's output; it is not one cartridge in
# isolation. Weighting by units is what turns "+3 g" into kilograms.
g = fw.giveaway([(3.0, 250), (3.0, 250)])
check(g["grams"] == 1500.0, "3 g across 500 units is 1500 g")
check(g["kg"] == 1.5, "reported in kg too")
check(g["mean_deviation"] == 3.0, "mean deviation is per unit, not per reading")
check(g["samples"] == 2 and g["units_represented"] == 500, "sample and unit counts")
mixed = fw.giveaway([(6.0, 300), (-2.0, 100)])
check(mixed["grams"] == 1600.0, "under-target readings offset over-target ones")
check(fw.giveaway([])["grams"] == 0.0, "no readings is zero, not a crash")
check(fw.giveaway(None)["samples"] == 0, "None is survivable")
check(fw.giveaway([(None, 10), ("x", 5), (2.0, None)])["samples"] == 1,
      "malformed rows are skipped, the good one still counts")
print("  aggregation is unit-weighted and survives junk")

# -------------------------------------------------------------- database --
section("6. THE COLUMNS EXIST AND THE WRITE PATH FILLS THEM")
import crud  # noqa: E402
from db_core import engine  # noqa: E402
from models import ProductionLog  # noqa: E402

with engine.connect() as conn:
    cols = {r[0] for r in conn.execute(sa.text(
        "SELECT column_name FROM information_schema.columns "
        "WHERE table_name = 'production_logs'"))}
for c in ("check_weight_g", "weight_deviation_g", "weight_status"):
    check(c in cols, f"production_logs.{c} exists")

runs = crud.get_assigned_runs_df()
row = runs[runs["pump_station"] == "Pump 1"].iloc[0]
STATION, RESIN, CART = row["pump_station"], row["resin_type"], row["cartridge_type"]
LOT = str(row["lot_number"])

before = len(crud.get_production_logs_df())
crud.add_hourly_log(
    operator_name="Weight Tester", pump_station=STATION, shift="Shift 1",
    cartridge_type=CART, resin_type=RESIN, lot_number=LOT,
    bottles=200, scrap_empty=0, scrap_filled=0, notes="weighed",
    weight=fw.judge(1113, SPEC),
)
# and one with no reading at all - the common case
crud.add_hourly_log(
    operator_name="Weight Tester", pump_station=STATION, shift="Shift 1",
    cartridge_type=CART, resin_type=RESIN, lot_number=LOT,
    bottles=200, scrap_empty=0, scrap_filled=0, notes="not weighed",
)
after = crud.get_production_logs_df()
check(len(after) == before + 2, "both logs were written")

weighed = after[after["notes"] == "weighed"].iloc[0]
check(float(weighed["check_weight_g"]) == 1113.0, "the reading is stored")
check(float(weighed["weight_deviation_g"]) == 3.0, "the deviation is stored")
check(weighed["weight_status"] == "in", "the status judged at capture is stored")

unweighed = after[after["notes"] == "not weighed"].iloc[0]
import pandas as pd  # noqa: E402
check(pd.isna(unweighed["check_weight_g"]), "a log with no reading stores NULL")
check(pd.isna(unweighed["weight_status"]), "and no status")
print("  a weighed log and an unweighed log both write correctly")

# Every caller that predates this keeps working untouched.
crud.add_hourly_log(
    operator_name="Weight Tester", pump_station=STATION, shift="Shift 1",
    cartridge_type=CART, resin_type=RESIN, lot_number=LOT,
    bottles=10, scrap_empty=0, scrap_filled=0, notes="legacy caller",
    log_type="Packing Count",
)
check(True, "the pre-existing signature still accepts no weight argument")
print("  existing callers (admin, reconciliation, gateway) are unaffected")

# --------------------------------------------------------------- the page --
section("7. THE TWO RULES, AGAINST THE REAL PAGE")
from streamlit.testing.v1 import AppTest  # noqa: E402
import streamlit as _st  # noqa: E402

_st.page_link = lambda *a, **k: None
_st.logo = lambda *a, **k: None
_st.switch_page = lambda *a, **k: None

from crud import submit_daily_checklist, create_user  # noqa: E402
import uuid  # noqa: E402

OP = "Wei " + uuid.uuid4().hex[:6].upper()
create_user(OP.split()[1].lower(), f"{OP.split()[1].lower()}@x.com", "5555", OP, "operator")
submit_daily_checklist(OP, "Shift 1", STATION)

CART_LABEL = {"V1": "V1 (1L Cartridge)", "V2": "V2 (1L Cartridge)",
              "RPS": "RPS (5L Bulk Jug)"}.get(str(CART), "V1 (1L Cartridge)")


def open_form():
    at = AppTest.from_file(str(ROOT / "pages" / "Operator_Form.py"), default_timeout=90)
    # AppTest's session_state has no .update(); set keys one at a time.
    for k, v in {"authenticated": True, "user_name": OP,
                 "user_role": "operator", "user_shift": "Shift 1",
                 "user_id": 1, "username": OP.split()[1].lower(),
                 "h_pump": STATION}.items():
        at.session_state[k] = v
    at.run()
    at.selectbox(key="h_cart").set_value(CART_LABEL).run()
    at.selectbox(key="h_resin").set_value(RESIN).run()
    at.text_input(key="h_lot_entered").set_value(f"L-{LOT}").run()
    return at


def submit_of(at):
    return [b for b in at.button if "SUBMIT POURING LOG" in b.label][0]


at = open_form()
check(at.exception == [], "the page renders with the weight field present")
weight_widgets = [n for n in at.number_input if n.key == "h_weight"]
check(len(weight_widgets) == 1, "there is exactly one check-weight field")

# RULE 2 - never pre-filled.
check(weight_widgets[0].value is None,
      "the weight box is EMPTY on load - a pre-filled target gets accepted, not measured")

# RULE 1 - never blocks, with nothing typed.
check(getattr(submit_of(at), "disabled", None) is False,
      "submit is enabled with NO weight entered - the reading is optional")
print("  empty on arrival, and an empty reading does not block the log")

# ...and still does not block when the reading is bad news.
at.number_input(key="h_weight").set_value(99000.0).run()   # unambiguously over any spec
body = "\n".join(str(e.value) for grp in (at.markdown, at.caption, at.error, at.warning)
                 for e in grp)
check(getattr(submit_of(at), "disabled", None) is False,
      "an OUT-OF-BAND weight still does not block submission")
check("Over the high limit" in body, "the operator is told it is over, immediately")
check(at.exception == [], "no exception on an out-of-band reading")
print("  an out-of-band reading informs the operator and blocks nothing")

# Derive an in-band value from the resin the page is actually showing, rather
# than assuming it shares the constant used earlier in this file. The whole
# point of the feature is that each resin has its own window; a test that
# hardcodes one is testing a different resin than the operator sees.
_specs = crud.get_all_resin_specs_df("ALL")
_match = _specs[_specs["resin_name"] == RESIN]
PAGE_SPEC = fw.spec_from_row(_match.iloc[0]) if not _match.empty else None
check(PAGE_SPEC is not None, f"the page's resin ({RESIN}) has a spec on file to judge against")
ON_TARGET = PAGE_SPEC["target"]
check(fw.judge(ON_TARGET, PAGE_SPEC)["status"] == fw.IN, "its own target is in its own band")

at2 = open_form()
at2.number_input(key="h_weight").set_value(float(ON_TARGET)).run()
body2 = "\n".join(str(e.value) for grp in (at2.markdown, at2.caption) for e in grp)
check("In band" in body2, "an in-band reading is confirmed on screen")
check(getattr(submit_of(at2), "disabled", None) is False, "and submit stays enabled")
print(f"  live feedback appears as the number is typed ({RESIN} target {ON_TARGET:g} g)")

section("THE IN-BAND HEADLINE NEVER ROUNDS AWAY THE EXCEPTION")
# 349 of 350 is 99.71%, which a ".0f" prints as "100%" - directly above a
# scatter plot in which the one out-of-band point is plainly visible. The
# exception is the reason the panel exists.
check(fw.band_percent(349, 350) == "99.7%", "349 of 350 reads as what it is, not as 100%")
# The clamp matters only once the true value rounds to 100 at one decimal:
# 9999/10000 is 99.99%, which "%.1f" would print as "100.0%".
check(fw.band_percent(9999, 10000) == "99.9%", "a share that rounds to 100 is held below it")
check(fw.band_percent(350, 350) == "100%", "an actual clean sweep does read 100%")
check(fw.band_percent(1, 1000) == "0.1%", "and a lone success never reads as 0%")
check(fw.band_percent(0, 350) == "0%", "while none in band does read 0%")
check(fw.band_percent(0, 0) == "\u2014", "nothing judged yet is a dash, not a division by zero")
check(fw.band_percent(175, 350) == "50.0%", "an ordinary share prints with a decimal")
check(fw.band_percent(None, 350) == "\u2014", "junk in gives a dash, not an exception")
check(fw.band_percent(400, 350) == "100%", "more in-band than judged is clamped rather than over 100%")
print("  the headline agrees with the plot")

section("RESULT")
print(f"ALL {CHECKS} FILL WEIGHT ASSERTIONS PASSED")
