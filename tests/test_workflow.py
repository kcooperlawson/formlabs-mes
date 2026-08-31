"""Full-floor simulation against the real crud.py on a real Postgres.

Managers create runs, operators clear station checklists and pour, the lot
gate passes/fails/gets rejected, packing and downtime land, and then every
number the UI shows is recomputed from the raw logs and compared.
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _boot import boot
srv, uri = boot()

import crud
from crud import *
from datetime import date, datetime, timedelta

FAILS, CHECKS = [], 0
def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  ✗ {label}\n      got:      {got!r}\n      expected: {exp!r}")
    return got == exp

def section(t):
    print(f"\n{'='*66}\n{t}\n{'='*66}")

# ===================================================================== SETUP
section("1. PLANT SETUP  (admin seeds stations, resins, reactor, people)")
for p in ("Pump 1", "Pump 2", "Pump 3", "Pack-Out Station"):
    add_pump_station(p)
add_reactor("Reactor 1", 5000)
add_resin_spec("V1", "RS-C1-DRGY-05", "FLDRGY05", "Draft Grey V5", 1000.0, 990.0, 1010.0, units_per_skid=400)
add_resin_spec("V2", "RS-C2-GPCL-05", "FLGPCL05", "Standard Clear V5", 1110.0, 1100.0, 1115.0, units_per_skid=500)
add_resin_spec("RPS", "RS-R5-GPBK-05", "FLGPBK05", "Standard Black V5", 5000.0, 4950.0, 5050.0, units_per_skid=100)
create_user("maria", "maria@x.com", "1111", "Maria Vega", "manager")
create_user("ana",   "ana@x.com",   "2222", "Ana Ruiz",   "operator")
create_user("bo",    "bo@x.com",    "3333", "Bo Chen",    "operator")
create_user("cy",    "cy@x.com",    "4444", "Cy Patel",   "packer")
# crud.py seeds demo stations/users on first boot, so assert presence, not equality
_pumps = set(get_active_pumps())
check("my stations registered", {"Pump 1", "Pump 2", "Pump 3", "Pack-Out Station"} <= _pumps, True)
_resins = set(get_all_resin_specs_df("ALL")["resin_name"])
check("my resins on file", {"Draft Grey V5", "Standard Clear V5", "Standard Black V5"} <= _resins, True)
check("my operators available", {"Ana Ruiz", "Bo Chen"} <= set(get_active_operators()), True)
print(f"  {len(_pumps)} stations, {len(_resins)} resins")

# ============================================================ MANAGER: RUNS
section("2. MANAGER CREATES WORK ORDERS")
GREY_LOT, CLEAR_LOT = "2411A0742", "2503C0088"
create_assigned_run("Reactor 1", 5000, "Draft Grey V5",     "V1",  1000, "Ana Ruiz", "Pump 1", GREY_LOT,  "")
create_assigned_run("Reactor 1", 5000, "Standard Clear V5", "V2",   800, "Bo Chen",  "Pump 2", CLEAR_LOT, "")
create_assigned_run("Reactor 1", 5000, "Standard Black V5", "RPS",  400, "Bo Chen",  "Pump 3", "",        "")
runs = get_assigned_runs_df()
# create_assigned_run returns the auto-detected unit count, not the row id
r1 = int(runs[runs["pump_station"] == "Pump 1"]["id"].iloc[0])
r2 = int(runs[runs["pump_station"] == "Pump 2"]["id"].iloc[0])
r3 = int(runs[runs["pump_station"] == "Pump 3"]["id"].iloc[0])
check("three runs created", len(runs), 3)
check("all start at zero units", list(runs["current_units"].unique()), [0])
print(f"  Pump 1 / V1 Grey  lot {GREY_LOT}  target 1000")
print(f"  Pump 2 / V2 Clear lot {CLEAR_LOT}  target 800")
print(f"  Pump 3 / RPS Black  no lot         target 400")

# ====================================================== STARTUP CHECKLISTS
section("3. STARTUP CHECKLIST  (per operator, per shift, per station)")
check("Ana locked out of Pump 1 at start", has_completed_daily_checklist("Ana Ruiz", "Shift 1", "Pump 1"), False)
submit_daily_checklist("Ana Ruiz", "Shift 1", "Pump 1")
check("Ana unlocked at Pump 1",            has_completed_daily_checklist("Ana Ruiz", "Shift 1", "Pump 1"), True)
check("Ana STILL locked at Pump 2",        has_completed_daily_checklist("Ana Ruiz", "Shift 1", "Pump 2"), False)
submit_daily_checklist("Ana Ruiz", "Shift 1", "Pump 2")
check("Ana unlocked at Pump 2 too",        has_completed_daily_checklist("Ana Ruiz", "Shift 1", "Pump 2"), True)
check("Pump 1 stays unlocked",             has_completed_daily_checklist("Ana Ruiz", "Shift 1", "Pump 1"), True)
check("Bo unaffected by Ana's checklists", has_completed_daily_checklist("Bo Chen", "Shift 1", "Pump 1"), False)
check("Ana on Shift 2 must redo it",       has_completed_daily_checklist("Ana Ruiz", "Shift 2", "Pump 1"), False)
submit_daily_checklist("Bo Chen", "Shift 1", "Pump 3")
submit_daily_checklist("Cy Patel", "Shift 1", "Pack-Out Station")
check("double-submit writes no dupe row",
      (submit_daily_checklist("Ana Ruiz", "Shift 1", "Pump 1"), len(get_todays_checklists_df()))[1], 4)
print("  4 checklist rows: Ana@P1, Ana@P2, Bo@P3, Cy@PackOut")

# ============================================== THE GATE'S DECISION RULE
# Mirrors the four lines in Operator_Form.py that pick a result, so the
# scenarios below drive the same branches the operator's screen would.
def decide(expected_lot, typed):
    if is_placeholder_lot(expected_lot):
        return "recorded"
    if not lots_match(expected_lot, typed):
        return "mismatch"
    return "verified"

def pour(op, station, cart, resin, expected_lot, typed, units,
         scrap_e=0, scrap_f=0, level="full", note=""):
    """One operator log, gated exactly the way the form gates it."""
    if cart == "RPS":                       # gate never renders for RPS
        return add_hourly_log(operator_name=op, pump_station=station, shift="Shift 1",
                              cartridge_type=cart, resin_type=resin, lot_number=expected_lot,
                              bottles=units, scrap_empty=scrap_e, scrap_filled=scrap_f,
                              notes=note, verification=None), None
    result = decide(expected_lot, typed)
    lot_on_log = typed if (result == "mismatch" or is_placeholder_lot(expected_lot)) else expected_lot
    reason = "Wrong pallet staged at the station — lead approved finishing the tote" if result == "mismatch" else None
    if result == "mismatch":
        note = f"⚠️ LOT MISMATCH — cartridge stamped L-{typed}, run expects {expected_lot}. {reason}\n{note}".strip()
    v = dict(operator_name=op, pump_station=station, shift="Shift 1", cartridge_type=cart,
             resin_type=resin, expected_lot=(None if is_placeholder_lot(expected_lot) else expected_lot),
             entered_lot=typed, result=result,
             check_level=("record" if result == "recorded" else level), reason=reason)
    matched = add_hourly_log(operator_name=op, pump_station=station, shift="Shift 1",
                             cartridge_type=cart, resin_type=resin, lot_number=lot_on_log,
                             bottles=units, scrap_empty=scrap_e, scrap_filled=scrap_f,
                             notes=note, verification=v)
    return matched, result

section("3b. STAMP NORMALISATION")
# The cartridge base is stamped L-<lot>. Operators type it verbatim, with or
# without the prefix, in whatever case and spacing they manage on a tablet.
for _typed in ("L-2411A0742", "l- 2411a0742", "L:2411A0742", "2411-A-0742", "2411a0742"):
    check(f"{_typed!r} reads as the run lot", lots_match(GREY_LOT, _typed), True)
check("a different lot never matches", lots_match(GREY_LOT, "L-2408B0119"), False)
check("one digit off never matches", lots_match(GREY_LOT, "L-2411A0743"), False)
print("  stamp normalisation: dash, colon, bare, spaced and mixed case all resolve")

section("4. OPERATORS RUN THE STATIONS")
# --- Ana, Pump 1, clean checks -------------------------------------------
m, r = pour("Ana Ruiz", "Pump 1", "V1", "Draft Grey V5", GREY_LOT, "L-2411A0742", 250, scrap_e=2)
check("clean check verifies", r, "verified")
check("clean log credits the run", m, True)
m, r = pour("Ana Ruiz", "Pump 1", "V1", "Draft Grey V5", GREY_LOT, "2411-a-0742", 200, level="fast")
check("stamp typed messily still matches", r, "verified")
check("fast-path log credits the run", m, True)
runs = get_assigned_runs_df()
check("Pump 1 run credited 450", int(runs[runs["id"] == r1]["current_units"].iloc[0]), 450)

# --- Ana, Pump 1, wrong cartridge ----------------------------------------
m, r = pour("Ana Ruiz", "Pump 1", "V1", "Draft Grey V5", GREY_LOT, "L-2408B0119", 180, scrap_f=3)
check("wrong lot flags a mismatch", r, "mismatch")
check("mismatch does NOT credit the run", m, False)
runs = get_assigned_runs_df()
check("Pump 1 run still at 450", int(runs[runs["id"] == r1]["current_units"].iloc[0]), 450)

# --- Ana catches one before pouring --------------------------------------
add_lot_verification(dict(operator_name="Ana Ruiz", pump_station="Pump 1", shift="Shift 1",
                          cartridge_type="V1", resin_type="Draft Grey V5", expected_lot=GREY_LOT,
                          entered_lot="L-2401Z0001", result="rejected", check_level="full",
                          reason="Cartridge pulled at the station before pouring"))

# --- Bo, Pump 2, clean; then a log with no run behind it ------------------
pour("Bo Chen", "Pump 2", "V2", "Standard Clear V5", CLEAR_LOT, "L-2503C0088", 300)
pour("Bo Chen", "Pump 2", "V2", "Standard Clear V5", CLEAR_LOT, "L-2503C0088", 260, level="fast", scrap_e=1)
placeholder = f"LOT-{date.today().strftime('%Y%m%d')}-01"
m, r = pour("Ana Ruiz", "Pump 2", "V2", "Standard Clear V5", placeholder, "L-2503C0088", 120)
check("no run lot -> recorded, not mismatch", r, "recorded")

# --- Bo, Pump 3, RPS: gate never applies ---------------------------------
m, r = pour("Bo Chen", "Pump 3", "RPS", "Standard Black V5", "", "", 150)
check("RPS pours with no gate", r, None)
check("RPS log still credits its run", m, True)

# --- downtime + packing ---------------------------------------------------
add_downtime_reason("Nozzle Clog")
add_downtime_log("Ana Ruiz", "Pump 1", "Shift 1", "Nozzle Clog", 25, "Flushed and restarted")
add_hourly_log(operator_name="Cy Patel", pump_station="Pack-Out Station", shift="Shift 1",
               cartridge_type="V1", resin_type="Draft Grey V5", lot_number=GREY_LOT,
               bottles=400, scrap_empty=0, scrap_filled=0, notes="Skid 1",
               log_type="Packing Count")
print("  9 production logs, 1 downtime, 5 lot checks written")

# ================================================================= NUMBERS
section("5. STATISTICAL OUTPUTS  (recomputed from raw logs)")
df = get_production_logs_df()
pours = df[df["log_type"] == "Hourly Bottle Count"]
packs = df[df["log_type"] == "Packing Count"]
poured = int(pours["bottles_filled"].sum())
scrap = int(pours["scrap_empty"].sum() + pours["scrap_filled"].sum())
packed = int(packs["bottles_filled"].sum())
yield_pct = poured / (poured + scrap) * 100

check("total poured units", poured, 250 + 200 + 180 + 300 + 260 + 120 + 150)
check("total scrap units", scrap, 2 + 3 + 1)
check("total packed units", packed, 400)
check("plant yield %", round(yield_pct, 3), round(1460 / 1466 * 100, 3))
check("floor WIP (poured - packed)", poured - packed, 1060)
print(f"  poured {poured} | scrap {scrap} | packed {packed} | yield {yield_pct:.2f}% | WIP {poured-packed}")

ana = pours[pours["operator_name"] == "Ana Ruiz"]
check("Ana's units", int(ana["bottles_filled"].sum()), 250 + 200 + 180 + 120)
check("Bo's units", int(pours[pours["operator_name"] == "Bo Chen"]["bottles_filled"].sum()), 300 + 260 + 150)

check("units credited to the Grey run", calculate_logged_units_for_resin("Draft Grey V5", "V1", "Pump 1", GREY_LOT), 450)
check("units credited to the Clear run", calculate_logged_units_for_resin("Standard Clear V5", "V2", "Pump 2", CLEAR_LOT), 560)
runs = get_assigned_runs_df()
for rid, exp in ((r1, 450), (r2, 560), (r3, 150)):
    check(f"run {rid} progress", int(runs[runs["id"] == rid]["current_units"].iloc[0]), exp)

sync_all_runs_with_logs()
runs = get_assigned_runs_df()
check("resync leaves Grey run unchanged", int(runs[runs["id"] == r1]["current_units"].iloc[0]), 450)

dt = get_downtime_logs_df()
check("downtime minutes", int(dt["duration_min"].sum()), 25)

section("6. LOT VERIFICATION REPORTING  (what the manager page renders)")
lv = get_lot_verifications_df(days=30)
counts = lv["result"].value_counts().to_dict()
check("verified checks", counts.get("verified"), 4)
check("mismatch checks", counts.get("mismatch"), 1)
check("recorded checks", counts.get("recorded"), 1)
check("rejected checks", counts.get("rejected"), 1)
check("total checks", len(lv), 7)
lvl = lv["check_level"].value_counts().to_dict()
check("full checks", lvl.get("full"), 4)
check("fast checks", lvl.get("fast"), 2)
check("record-only checks", lvl.get("record"), 1)
flagged = lv[lv["result"].isin(["mismatch", "expired", "rejected"])]
check("flag rate", round(len(flagged) / len(lv) * 100, 1), round(2 / 7 * 100, 1))
check("rejection has no production log", bool(lv[lv["result"] == "rejected"]["production_log_id"].isna().all()), True)
check("every pour check links to its log",
      int(lv[lv["result"] != "rejected"]["production_log_id"].notna().sum()), 6)

mm = lv[lv["result"] == "mismatch"].iloc[0]
check("mismatch stores what was expected", mm["expected_lot"], GREY_LOT)
check("mismatch stores what was read", mm["entered_lot"], "L-2408B0119")
check("mismatch carries a reason", bool(str(mm["reason"]).strip()), True)
mlog = df[df["id"] == int(mm["production_log_id"])].iloc[0]
check("mismatched log carries verify_status", mlog["verify_status"], "mismatch")
check("mismatched log carries the CARTRIDGE lot", mlog["lot_number"], "L-2408B0119")
check("mismatched log explains itself in notes", "LOT MISMATCH" in str(mlog["notes"]), True)
check("clean logs are marked verified", int((df["verify_status"] == "verified").sum()), 4)
check("RPS log has no verify_status", bool(df[df["cartridge_type"] == "RPS"]["verify_status"].isna().all()), True)
print("  " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))

section("7. RECONCILIATION")
before = calculate_logged_units_for_resin("Draft Grey V5", "V1", "", GREY_LOT)
check("grey lot poured under its own lot", before, 450)
reconcile_pouring_to_packing(GREY_LOT, 420)
after_df = get_production_logs_df()
# the balancing row is a normal Hourly Bottle Count booked to a system pseudo-operator,
# which is how operator metrics stay untouched by a plant-level correction
adj = after_df[after_df["operator_name"] == "System Auto-Reconciliation"]
check("one reconciliation row written", len(adj), 1)
check("it carries the variance", int(adj["bottles_filled"].iloc[0]), 420 - 450)
check("it is not attributed to an operator",
      int(after_df[after_df["operator_name"] == "Ana Ruiz"]["bottles_filled"].sum()), 750)
check("grey lot now balances to packing", calculate_logged_units_for_resin("Draft Grey V5", "V1", "", GREY_LOT), 420)
# the mismatched pour was booked under the CARTRIDGE lot, so it is correctly
# excluded from the run lot's reconciliation rather than silently absorbed
check("mismatched pour excluded from this lot",
      int(after_df[after_df["lot_number"] == "L-2408B0119"]["bottles_filled"].sum()), 180)
print(f"  grey lot poured {before} -> packed 420, variance row: {int(adj['bottles_filled'].iloc[0])} units")

# ===================================================================== DONE
section("RESULT")
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} checks FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} WORKFLOW ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
