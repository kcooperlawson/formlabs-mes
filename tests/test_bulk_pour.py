"""Pours measured as an amount, and the ways that goes wrong quietly.

A container count is self-checking: an operator who types 2500 cartridges
knows they did not fill 2500 cartridges. A measured amount is not. 1800 typed
instead of 180 looks exactly as ordinary in a number box, and the first sign
of it is a vessel reading empty on the wall display an hour later - by which
time the number is in the record and the tank it came out of is wrong until
somebody works out why.

So the conversion, the arithmetic and the sanity check are plain functions on
plain numbers, checked here against the cases that actually cost something:

  A kilogram is not a litre, and resin is bought in one and stored in the
  other. Getting the direction of that conversion backwards is a 23% error
  that looks entirely plausible on every screen.

  A measured amount must beat the container count outright wherever a total
  is worked out - and every existing row has no measured amount, so nothing
  already recorded may change meaning. Both halves of that are asserted,
  because a regression in either is silent.

  A pour bigger than the tank is a typo. A pour bigger than what the record
  thinks is LEFT in the tank usually is not: the vessel was topped up without
  the new lot being logged yet, which happens, and refusing that pour would
  mean the record is wrong and the operator cannot fix it.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import bulk_pour as bp  # noqa: E402

FAILS, CHECKS = [], 0


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


def near(label, got, exp, tol=0.01):
    global CHECKS
    CHECKS += 1
    if abs(float(got) - float(exp)) > tol:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: ~{exp!r}")


# The real container sizes, as crud defines them.
def litres_of(fmt):
    f = str(fmt or "").strip().upper()
    return 5.0 if "RPS" in f else (0.124 if "PIGMENT" in f else 1.0)


print("=" * 66)
print("POURS MEASURED RATHER THAN COUNTED")
print("=" * 66)

# --- density, derived from specs nobody wrote as a density -------------------
# A spec of 1,110 g in a 1 L cartridge and 5,550 g in a 5 L jug are the same
# resin at the same density. That is the whole reason this is derived per
# resin rather than looked up per format.
specs = [
    {"resin_name": "Clear V5", "cartridge_type": "V2", "actual_spec_g": 1110.0},
    {"resin_name": "Clear V5", "cartridge_type": "RPS", "actual_spec_g": 5550.0},
    {"resin_name": "Tough 2000", "cartridge_type": "RPS", "actual_spec_g": 5250.0},
]
d = bp.density_map(specs, litres_of)
near("a 1 L spec gives kilograms per litre", d["clear v5"], 1.11)
near("and a 5 L spec of the same resin gives the same answer", d["clear v5"], 1.11)
near("a resin only registered as a jug still resolves", d["tough 2000"], 1.05)
check("two formats of one resin are one entry, not two", len(d), 2)

check("a resin nobody has a spec for falls back rather than failing",
      bp.resin_density("Never Heard Of It", d), bp.DEFAULT_DENSITY_KG_L)
check("and so does a missing name", bp.resin_density(None, d), bp.DEFAULT_DENSITY_KG_L)
check("a resin with a spec uses it", round(bp.resin_density("clear v5", d), 3), 1.11)
check("the name is matched however it is cased",
      bp.resin_density("CLEAR V5", d), bp.resin_density("clear v5", d))

# A spec table with rubbish in it must not poison the map.
bad = bp.density_map([
    {"resin_name": "Zero", "cartridge_type": "V2", "actual_spec_g": 0},
    {"resin_name": "", "cartridge_type": "V2", "actual_spec_g": 1110},
    {"wrong": "shape"},
], litres_of)
check("a spec with no weight is skipped rather than stored as zero", "zero" in bad, False)
check("a row with no name is skipped", len(bad), 0)
check("and a row of the wrong shape does not raise", isinstance(bad, dict), True)
print("  density OK")

# --- litres from kilograms ---------------------------------------------------
check("litres pass straight through", bp.to_litres(180, "L", 1.11), 180.0)
near("kilograms are divided by density, not multiplied", bp.to_litres(200, "kg", 1.11), 180.18)
# The direction matters: resin is heavier than water, so a kilogram is LESS
# than a litre. Multiplying instead would give 222 and look just as plausible.
check("so 200 kg is fewer litres, not more", bp.to_litres(200, "kg", 1.11) < 200, True)
near("a heavier resin gives fewer litres for the same weight",
     bp.to_litres(200, "kg", 1.20), 166.67)
check("kg is recognised however it is written",
      bp.to_litres(100, "KG", 1.0), bp.to_litres(100, "kilograms", 1.0))
check("a zero density cannot divide by zero",
      bp.to_litres(111, "kg", 0) > 0, True)
check("nothing poured is no litres", bp.to_litres(0, "kg", 1.11), 0.0)
check("a negative amount is no litres, not negative ones", bp.to_litres(-50, "L"), 0.0)
check("text where a number should be does not raise", bp.to_litres("lots", "L"), 0.0)
check("nor does nothing at all", bp.to_litres(None, "L"), 0.0)
print("  kilograms to litres OK")

# --- several containers ------------------------------------------------------
check("one drum is the amount in it", bp.pour_litres(1, 180, "L"), 180.0)
check("three identical drums are three times it", bp.pour_litres(3, 180, "L"), 540.0)
near("and the count applies after the conversion, not before",
     bp.pour_litres(2, 200, "kg", 1.11), 360.36)
check("a count below one is treated as one", bp.pour_litres(0, 180, "L"), 180.0)
check("as is a missing one", bp.pour_litres(None, 180, "L"), 180.0)
print("  containers OK")

# --- the check that catches a typo -------------------------------------------
ok = bp.check_pour(180, capacity_l=5000, remaining_l=3200)
check("an ordinary pour passes", ok["ok"], True)
check("and says nothing, because there is nothing to say", ok["message"], "")

blank = bp.check_pour(0, capacity_l=5000)
check("no amount blocks the submit", blank["blocked"], True)

# The one this exists for.
typo = bp.check_pour(1800, capacity_l=1000, remaining_l=800)
check("more than the vessel holds is blocked", typo["blocked"], True)
check("and names the capacity, so the operator can see which is wrong",
      "1,000 L" in typo["message"], True)
check("and points at the unit as well as the number",
      "unit" in typo["message"], True)

check("an amount larger than any vessel on the floor is blocked even with no tank known",
      bp.check_pour(9000)["blocked"], True)

# More than the record thinks is left is suspicious, not impossible: a tank
# topped up without the new lot logged yet gives out more than the record says.
over = bp.check_pour(900, capacity_l=5000, remaining_l=400)
check("more than the record says is left is allowed", over["blocked"], False)
check("but it is said out loud", over["level"], "over-level")
check("and it explains the likely reason rather than just objecting",
      "refilled" in over["message"], True)

check("an unknown vessel does not invent a limit",
      bp.check_pour(400)["ok"], True)
check("and a pour exactly filling the vessel is fine",
      bp.check_pour(5000, capacity_l=5000)["blocked"], False)
print("  the sanity check OK")

# --- what the operator is told before submitting -----------------------------
line = bp.describe_pour(1, 200, "kg", 1.11, "55 gal drum")
check("the conversion is stated in litres", "180.2 L" in line, True)
check("in the operator's own words for the container", "55 gal drum" in line, True)
check("what they typed is repeated back unchanged", "200 kg" in line, True)
check("several containers are shown as a multiplication",
      "3 x 180" in bp.describe_pour(3, 180, "L", 1.11, "drum"), True)
check("and one container is not", "1 x" in bp.describe_pour(1, 180, "L", 1.11, "drum"), False)
check("a pour with no description still reads",
      "container" in bp.describe_pour(1, 180, "L", 1.11, ""), True)
print("  the confirmation line OK")

# --- the definition every total reads ----------------------------------------
# This is the one that decides whether a bulk pour reaches the tank, the shift
# build, the wall display and the exports - or reaches some of them.
check("an ordinary cartridge log is still count times format",
      bp.log_litres(250, "V2", None, litres_of), 250.0)
check("a jug log is still five litres apiece",
      bp.log_litres(40, "RPS (5L Bulk Jug)", None, litres_of), 200.0)
check("pigment is still a fraction of a litre",
      round(bp.log_litres(100, "Pigment", None, litres_of), 2), 12.4)

check("a measured amount wins outright",
      bp.log_litres(1, "Bulk", 180.0, litres_of), 180.0)
check("and it wins even when the count would say something bigger",
      bp.log_litres(3, "Bulk", 180.0, litres_of), 180.0)

# Every row written before this existed has no measured amount. If NULL were
# read as zero, every historical total in the plant would go to nothing.
check("a row from before this existed reads exactly as it always did",
      bp.log_litres(250, "V2", None, litres_of), 250.0)
check("and a zero measured amount does not beat the count either",
      bp.log_litres(250, "V2", 0, litres_of), 250.0)
check("nor does a negative one", bp.log_litres(250, "V2", -5, litres_of), 250.0)
check("nor does a NaN out of a dataframe column",
      bp.log_litres(250, "V2", float("nan"), litres_of), 250.0)
check("nor does an empty string out of a form",
      bp.log_litres(250, "V2", "", litres_of), 250.0)
print("  the one definition OK")

# --- the format list, and the trap in it -------------------------------------
# This section exists because of a real bug, caught by the interface tests and
# not by anything here: the form picked a format code with a chain of substring
# tests, and "RPS (5L Bulk Jug)" contains the word "Bulk". Adding a bulk option
# turned every 5-litre jug into a measured pour - a format that had been right
# for years, broken by a new option sharing a word with an old one. The
# arithmetic above would all still have passed.
# _boot before crud: importing crud opens a database, and without this that
# database is whatever .env points at - the live one on the plant PC.
import _boot  # noqa: E402,F401  (throwaway database, refuses production)
import crud  # noqa: E402

check("a jug is a jug, not a bulk pour, whatever its label says",
      crud.format_code("RPS (5L Bulk Jug)"), "RPS")
check("a V2 cartridge is a V2", crud.format_code("V2 (1L Cartridge)"), "V2")
check("a V1 is a V1", crud.format_code("V1 (1L Cartridge)"), "V1")
check("pigment is pigment", crud.format_code("Pigment"), "Pigment")
check("and only the measured-amount option is a bulk pour",
      crud.format_code(crud.BULK_FORMAT_LABEL), "Bulk")
check("a label nobody recognises falls back to a cartridge rather than raising",
      crud.format_code("something else"), "V2")
check("as does nothing at all", crud.format_code(None), "V2")

check("a plant that has not switched it on sees the four formats it always saw",
      crud.format_choices(False),
      ("V2 (1L Cartridge)", "V1 (1L Cartridge)", "RPS (5L Bulk Jug)", "Pigment"))
check("switching it on adds one option and moves none of the others",
      crud.format_choices(True)[:4], crud.format_choices(False))
check("and the added one is the measured-amount option",
      crud.format_choices(True)[-1], crud.BULK_FORMAT_LABEL)

# Every gated format must survive the mapping: a format that stops being
# recognised stops being lot-checked, and nothing on screen would say so.
for _label, _code in crud.CONTAINER_FORMATS.items():
    if _code != "Bulk":
        check(f"{_code} is still lot-checked", _code in crud.GATED_FORMATS, True)
check("and a bulk pour is not, because a drum carries no cartridge lot label",
      "Bulk" in crud.GATED_FORMATS, False)
print("  the format list OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} BULK POUR CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} BULK POUR ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
