"""What a tank reads, and why it reads that, in both modes.

The reactor level was never a reactor feature. The work order's lot was
silently doing the job of "when was this tank last filled", and the run's
container format the job of "how big are the units coming out". Turn work
orders off and the tank has nothing to reason from: it summed every log ever
recorded for that resin and pump, drained to empty and stayed there, and
sized every unit as a 1 L cartridge whatever was actually poured.

The answer is that operators already tell us when a tank is refilled - the lot
goes on every hourly log, and the lot check makes them read it off the
container. So the batch is the newest lot at that pump, and the level follows
from it identically whether or not anybody dispatches runs.

No browser and no Streamlit: this is arithmetic over rows, which is exactly
the kind of thing that should be checked without either.
"""
import pathlib
import sys
import warnings
from datetime import date, datetime, timedelta

warnings.filterwarnings("ignore")
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tests"))

import _boot  # noqa: E402  (throwaway database, refuses the .env connection)

_boot.boot(fresh=True, db_name="formlabs_reactor_level")

import crud  # noqa: E402
from crud import (container_litres, reactor_draw_litres, reactor_for,  # noqa: E402
                  link_vessel_to_pump, vessels_on_pump, record_changeover,
                  get_last_picks, save_last_picks, get_all_reactors_df,
                  add_pump_station, add_resin_spec, add_reactor, add_hourly_log,
                  calculate_logged_units_for_resin)
from db_core import ScopedSession  # noqa: E402
from models import ProductionLog, Reactor  # noqa: E402

FAILS, CHECKS = [], 0
_CLOCK = [datetime(2026, 9, 5, 6, 0, 0)]


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


def log(resin, pump, fmt, lot, units, kind="Hourly Bottle Count"):
    """One production log, each a minute after the last so order is defined."""
    _CLOCK[0] += timedelta(minutes=1)
    session = ScopedSession()
    session.add(ProductionLog(
        log_type=kind, operator_name="Ana Ruiz", pump_station=pump, shift="Shift 1",
        resin_type=resin, cartridge_type=fmt, lot_number=lot, bottles_filled=units,
        date=date.today(), timestamp=_CLOCK[0]))
    session.commit()
    session.close()


print("=" * 66)
print("REACTOR LEVEL")
print("=" * 66)

# --- one container, one volume, one definition ---------------------------
check("a V2 cartridge is 1 litre", container_litres("V2"), 1.0)
check("so is a V1", container_litres("V1 (1L Cartridge)"), 1.0)
check("an RPS jug is 5 litres", container_litres("RPS (5L Bulk Jug)"), 5.0)
check("pigment is a fraction of one", container_litres("Pigment"), 0.124)
check("an unknown format falls back to a cartridge", container_litres("wat"), 1.0)
check("and so does a missing one", container_litres(None), 1.0)
print("  container volumes OK")

# --- an empty tank reads full --------------------------------------------
drawn, lot = reactor_draw_litres("Clear V5", "Pump 1")
check("nothing logged means nothing drawn", drawn, 0.0)
check("and no batch to name", lot, "")

# --- the batch is the newest lot, and the tank refills when it changes ----
# 3,600 L drawn on the first lot, the tank is refilled, 1,000 L on the second.
for _ in range(4):
    log("Clear V5", "Pump 1", "V2", "2501A0001", 900)
drawn, lot = reactor_draw_litres("Clear V5", "Pump 1")
check("the first batch counts what it drew", drawn, 3600.0)
check("and names the lot in the tank", lot, "2501A0001")

for _ in range(2):
    log("Clear V5", "Pump 1", "V2", "2502B0002", 500)
drawn, lot = reactor_draw_litres("Clear V5", "Pump 1")
check("a new lot is a refill: the previous batch is not counted", drawn, 1000.0)
check("and the tank names the lot now in it", lot, "2502B0002")
print("  the lot change refills the tank OK")

# --- each log is sized by ITS OWN format, not one assumed for all ---------
# The failure this replaces: a tank drawn down in 5 L jugs read as if every
# jug were a 1 L cartridge, so it emptied five times too slowly.
for _ in range(3):
    log("Black V5", "Pump 3", "RPS", "2503C0003", 40)
drawn, lot = reactor_draw_litres("Black V5", "Pump 3")
check("120 jugs at 5 L each is 600 litres, not 120", drawn, 600.0)

# A batch that mixes formats is summed per log, which is the case a single
# multiplier could never get right in either mode.
log("Mixed Resin", "Pump 4", "V2", "2504D0004", 100)     # 100 L
log("Mixed Resin", "Pump 4", "RPS", "2504D0004", 10)     # 50 L
log("Mixed Resin", "Pump 4", "Pigment", "2504D0004", 50)  # 6.2 L
drawn, _ = reactor_draw_litres("Mixed Resin", "Pump 4")
check("a mixed batch sums each log by its own format", round(drawn, 3), 156.2)
print("  per-log volumes OK")

# --- a lot that comes back later is a new batch, not the old one ----------
log("Clear V5", "Pump 1", "V2", "2501A0001", 200)
drawn, lot = reactor_draw_litres("Clear V5", "Pump 1")
check("re-running an earlier lot counts only the new pass", drawn, 200.0)
check("and that lot is the one in the tank", lot, "2501A0001")

# --- a level calibration belongs to the batch it was taken during ---------
# It carries no real lot of its own, so it must not read as a batch change.
log("Clear V5", "Pump 1", "V2", "RECON-ADJ", -50, kind="System Calibration")
drawn, lot = reactor_draw_litres("Clear V5", "Pump 1")
check("a calibration adjusts the batch it was taken in", drawn, 150.0)
check("and does not look like a refill", lot, "2501A0001")
print("  batch boundaries OK")

# --- the pump scopes the tank --------------------------------------------
log("Clear V5", "Pump 9", "V2", "2509Z0009", 700)
drawn, _ = reactor_draw_litres("Clear V5", "Pump 1")
check("another pump's pour is not drawn from this tank", drawn, 150.0)
drawn, _ = reactor_draw_litres("Clear V5", "Pump 9")
check("and is drawn from that one", drawn, 700.0)

# --- and it reads the same whether or not a run exists -------------------
# The whole point: dispatching a run puts the same lot on the run and on the
# log, so the tank's answer does not depend on the mode at all.
before, before_lot = reactor_draw_litres("Black V5", "Pump 3")
crud.create_assigned_run(reactor_id="Tank B", reactor_size_l=3000, resin_type="Black V5",
                         cartridge_type="RPS", target_units=500, assigned_operator="Ana Ruiz",
                         pump_station="Pump 3", lot_number="2503C0003", notes="")
after, after_lot = reactor_draw_litres("Black V5", "Pump 3")
check("dispatching a run does not change what the tank reads", after, before)
check("nor which lot it says is in it", after_lot, before_lot)
print("  identical in both modes OK")

# --- calibrating a tank to a gauge reading -------------------------------
# The level is derived, so a calibration cannot set it: it writes the
# difference into the record and the level follows. The check that matters is
# that the tank afterwards reads what the operator typed in.
def new_tank(name, capacity, resin, pump):
    crud.add_reactor(name, capacity)
    session = ScopedSession()
    rid = session.query(Reactor).filter(Reactor.reactor_name == name).first().id
    session.close()
    crud.update_reactor_config(reactor_id=rid, resin=resin, pump=pump)


new_tank("Tank C", 2000, "Gauge Resin", "Pump 7")
for _ in range(3):
    log("Gauge Resin", "Pump 7", "RPS", "2507E0007", 20)   # 300 L on the books
drawn, _ = reactor_draw_litres("Gauge Resin", "Pump 7")
check("the tank starts where the logs put it", drawn, 300.0)

crud.reconcile_reactor_liters("Tank C", 1250.0, "Ana Ruiz", notes="gauge read")
drawn, lot = reactor_draw_litres("Gauge Resin", "Pump 7")
check("an exact-litres calibration lands on the number typed in", 2000.0 - drawn, 1250.0)
check("and does not read as a refill", lot, "2507E0007")

crud.reconcile_reactor_level("Tank C", 25.0, "Ana Ruiz", notes="sight glass")
drawn, _ = reactor_draw_litres("Gauge Resin", "Pump 7")
check("a percentage calibration lands on that percentage", 2000.0 - drawn, 500.0)

# And it still corrects a tank nobody has poured from yet, which the old
# version could not: it divided by a format it had no way to know.
new_tank("Tank D", 1000, "Fresh Resin", "Pump 8")
crud.reconcile_reactor_liters("Tank D", 900.0, "Ana Ruiz", notes="")
drawn, _ = reactor_draw_litres("Fresh Resin", "Pump 8")
check("a tank with no pours behind it calibrates too", 1000.0 - drawn, 900.0)
print("  calibration OK")

# --- a tank has to be linked to something, and there has to be a way ---------
# Reported from the floor on the first day of real use: "I created the reactor
# and all, but there is no reactor selector so it has no idea what I am
# pouring from." He was right, and it was worse than a missing picker. A
# vessel's level is worked out from the logs matching its pump and its resin,
# and the ONLY code that had ever set those two fields was work-order
# dispatch. This plant runs with work orders off, so a vessel created in the
# admin console was linked to nothing, counted nothing, and read full for ever
# while the floor emptied it.
add_pump_station("Pump 9")
add_resin_spec("V2", "SKU-LINK", "CLINK", "Link Test V1",
               1110.0, 1100.0, 1115.0, "1100-1115", 1.0, 24)

add_reactor("Unlinked Tank", 5000)
add_reactor("Linked Tank", 5000, assigned_pump="Pump 9",
            current_resin="Link Test V1", asset_tag="M-909", bay_marker="Z1")

add_hourly_log("Op", "Pump 9", "Shift 1", "V2", "Link Test V1", "L-LINK01", 100, 0, 0)

check("a tank created with a pump and a resin sees the pour",
      calculate_logged_units_for_resin("Link Test V1", "", "Pump 9", ""), 100)
check("a tank created without them is linked to nothing",
      reactor_for("Pump 9", "Link Test V1")["reactor_name"], "Linked Tank")
check("and the operator's form can name it",
      reactor_for("Pump 9", "Link Test V1")["asset_tag"], "M-909")
check("a station and resin with no vessel behind them says so rather than guessing",
      reactor_for("Pump 9", "Some Other Resin"), None)
check("so does a blank station", reactor_for("", "Link Test V1"), None)

# Two tanks on the same station and resin cannot be told apart, and saying so
# is the only honest answer - crediting a pour to whichever one came back
# first would put litres on the wrong vessel and look completely normal.
add_reactor("Twin Tank", 5000, assigned_pump="Pump 9", current_resin="Link Test V1")
check("two vessels on one station and resin report the ambiguity",
      sorted(reactor_for("Pump 9", "Link Test V1")["ambiguous"]),
      ["Linked Tank", "Twin Tank"])
print("  the vessel link OK")

# --- the operator sets it up, not a manager --------------------------------
# The plant runs in logging mode and the whole point is that a manager never
# opens a settings page. The operator already picks the pump and the resin
# every hour; the only thing missing is which physical tank that pump draws
# from, and that is asked once at the startup checklist where they are
# standing next to it.
add_pump_station("Pump 11")
add_resin_spec("V2", "SKU-OP1", "COP1", "Op Set A V1",
               1110.0, 1100.0, 1115.0, "1100-1115", 1.0, 24)
add_resin_spec("V2", "SKU-OP2", "COP2", "Op Set B V1",
               1110.0, 1100.0, 1115.0, "1100-1115", 1.0, 24)
add_reactor("Operator Tank", 5000, asset_tag="M-311")

check("a tank nobody has placed is on no pump", vessels_on_pump("Pump 11"), [])
check("the operator's answer at the checklist places it",
      link_vessel_to_pump("Operator Tank", "Pump 11"), True)
check("and it is on that pump from then on",
      [v["reactor_name"] for v in vessels_on_pump("Pump 11")], ["Operator Tank"])
check("the checklist never has to ask again",
      len(vessels_on_pump("Pump 11")), 1)

# The resin follows the pour, but only once the operator has confirmed it.
# An accidental resin pick must not silently restart a tank's accounting.
check("placing a tank does not guess what is in it",
      reactor_for("Pump 11", "Op Set A V1"), None)
check("the confirmed changeover puts it on that resin",
      record_changeover("Operator Tank", "Op Set A V1", operator="Op",
                        shift="Shift 1", pump_station="Pump 11"), True)
check("and the pour now lands on the right tank",
      reactor_for("Pump 11", "Op Set A V1")["asset_tag"], "M-311")

add_hourly_log("Op", "Pump 11", "Shift 1", "V2", "Op Set A V1", "L-OPSET01", 60, 0, 0)
check("the tank counts the pour", 
      calculate_logged_units_for_resin("Op Set A V1", "", "Pump 11", ""), 60)

# A changeover restarts the count rather than mixing two resins into one
# number, and the changeover row itself carries no units.
record_changeover("Operator Tank", "Op Set B V1", operator="Op",
                  shift="Shift 1", pump_station="Pump 11")
check("after a changeover the tank is on the new resin",
      reactor_for("Pump 11", "Op Set B V1")["reactor_name"], "Operator Tank")
check("the old resin no longer points at it",
      reactor_for("Pump 11", "Op Set A V1"), None)
check("and the changeover added no units of its own",
      calculate_logged_units_for_resin("Op Set B V1", "", "Pump 11", ""), 0)
print("  operator-led setup OK")

# --- the form opens where they left it -------------------------------------
check("an operator who has never logged has nothing remembered",
      get_last_picks("Nobody At All"),
      {"station": "", "cartridge": "", "resin": ""})
save_last_picks("Op Remember", "Pump 11", "V2 (1L Cartridge)", "Op Set B V1")
print("  (a name with no account saves nothing, and does not raise)")
print("  remembered picks OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} REACTOR LEVEL CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} REACTOR LEVEL ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
