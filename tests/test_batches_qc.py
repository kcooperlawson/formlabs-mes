"""Batches in a vessel, and the QC round trip attached to them.

Management asked three questions - when did resin go to QC, when did it come
back, how long did it sit in the reactor - and they are all durations. A
duration needs two ends, and a tank level worked out from the logs has neither.
So a filling of a vessel is a row now, and this checks the row behaves.

The cases that matter are the ones that produce a wrong NUMBER rather than an
error, because a wrong number on a management report gets acted on:

  * two open fillings on one vessel, which makes every later duration a guess
    about which one somebody meant
  * a QC result timed before the sample went out, which averages as a negative
  * a filling with no start time, which must read as unknown rather than as
    zero hours old
  * a changeover, which has to close one filling and open the next by itself,
    because that is the whole reason the reactor half needs nothing typed
"""
import pathlib
import sys
from datetime import datetime, timedelta

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import _boot  # noqa: E402  (throwaway database, refuses production)

import crud  # noqa: E402
from db_core import ScopedSession  # noqa: E402
from models import ReactorBatch  # noqa: E402

FAILURES, COUNT = [], 0


def check(cond, what):
    global COUNT
    COUNT += 1
    if not cond:
        FAILURES.append(what)
        print(f"  FAIL  {what}")


VESSEL = "QC Test Vessel"
PUMP = "Pump QC"
RESIN_A, RESIN_B = "QC Resin A", "QC Resin B"


def wipe():
    s = ScopedSession()
    s.query(ReactorBatch).filter(ReactorBatch.reactor_name == VESSEL).delete(
        synchronize_session=False)
    s.commit(); s.close()


# ------------------------------------------------------------- one filling --
print("\nOne filling of one vessel")
wipe()

start = datetime.now() - timedelta(hours=30)
bid = crud.open_batch(VESSEL, RESIN_A, pump_station=PUMP, filled_at=start,
                      by="Tester")
check(bid > 0, "a filling can be opened")

live = crud.current_batch(VESSEL)
check(live.get("id") == bid, "and is the one the vessel reports as current")
check(live.get("open") is True, "it is open")
check(29 <= (live.get("hours_in_reactor") or 0) <= 31,
      f"and it has been in the tank about 30 hours (got {live.get('hours_in_reactor')})")

again = crud.open_batch(VESSEL, RESIN_B, pump_station=PUMP)
check(again == 0, "a second filling cannot be opened while one is open")
check(crud.current_batch(VESSEL)["resin_type"] == RESIN_A,
      "and the open one is untouched by the attempt")

# ---------------------------------------------------------------- the QC --
print("\nThe QC round trip")

sent = datetime.now() - timedelta(hours=26)
ok, msg = crud.set_batch_qc(bid, sent_at=sent, by="Manager")
check(ok, f"a sample can be recorded as sent ({msg})")
live = crud.current_batch(VESSEL)
check(live["qc_open"] is True, "the batch reads as waiting on QC")
check(25 <= (live["hours_at_qc"] or 0) <= 27,
      "and the wait is counted to now while it is still out")
check(live["qc_result"] == "", "with no result yet")

back = sent + timedelta(hours=20)
ok, msg = crud.set_batch_qc(bid, sent_at=sent, result_at=back, result="pass",
                            note="within spec", by="Manager")
check(ok, f"and the result can be recorded ({msg})")
live = crud.current_batch(VESSEL)
check(live["qc_open"] is False, "it is no longer waiting")
check(live["qc_result"] == "pass", "the result is on it")
check(19.5 <= (live["hours_at_qc"] or 0) <= 20.5,
      f"and QC had it for 20 hours (got {live['hours_at_qc']})")
check(live["qc_by"] == "Manager", "with the name of whoever entered it")

# The ones that would produce a number nobody should trust.
ok, msg = crud.set_batch_qc(bid, sent_at=back, result_at=sent, result="pass")
check(not ok and "before" in msg,
      "a result timed before the sample went out is refused")
ok, msg = crud.set_batch_qc(bid, sent_at=sent, result="pass")
check(not ok, "so is a result with no time on it")
ok, msg = crud.set_batch_qc(bid, sent_at=sent, result_at=back, result="maybe")
check(not ok, "and a result that is not one of the three")
check(crud.current_batch(VESSEL)["qc_result"] == "pass",
      "none of which changed what was already recorded")

# ------------------------------------------------------------- closing it --
print("\nClosing a filling")

check(crud.close_batch(VESSEL, by="Tester") is True, "a filling can be closed")
done = crud.get_batches(reactor_name=VESSEL)[0]
check(done["open"] is False, "and reads as closed")
check(29 <= (done["hours_in_reactor"] or 0) <= 32,
      "with the time it spent in the vessel fixed at what it was")
check(crud.current_batch(VESSEL) == {}, "the vessel has no open filling now")
check(crud.close_batch(VESSEL) is False,
      "and closing again is a no, not an error")

# ------------------------------------------------- a changeover does it all --
print("\nA changeover closes one and opens the next")
wipe()

crud.add_pump_station(PUMP)
crud.add_resin_spec("V2", "SKU-QC-A", "CQCA", RESIN_A, 1110.0, 1100.0, 1115.0,
                    "1100-1115", 1.0, 24)
crud.add_resin_spec("V2", "SKU-QC-B", "CQCB", RESIN_B, 1110.0, 1100.0, 1115.0,
                    "1100-1115", 1.0, 24)
_existing = crud.get_all_reactors_df()
if _existing.empty or VESSEL not in set(_existing["reactor_name"]):
    crud.add_reactor(VESSEL, 5000, assigned_pump=PUMP, current_resin=RESIN_A)
crud.open_batch(VESSEL, RESIN_A, pump_station=PUMP,
                filled_at=datetime.now() - timedelta(hours=5), by="Tester")

check(crud.record_changeover(VESSEL, RESIN_B, operator="Ana", pump_station=PUMP) is True,
      "a changeover is recorded")
live = crud.current_batch(VESSEL)
check(live.get("resin_type") == RESIN_B,
      "the vessel's open filling is the new resin")
_new_age = live.get("hours_in_reactor")
check(_new_age is not None and _new_age < 1,
      f"and its clock starts at the changeover, not at the old filling "
      f"(got {_new_age})")
closed = [b for b in crud.get_batches(reactor_name=VESSEL) if not b["open"]]
check(len(closed) == 1, "the previous filling was closed")
check(4 <= (closed[0]["hours_in_reactor"] or 0) <= 6,
      "with the five hours it actually sat there")

# ------------------------------------------------ what the operator form asks --
print("\nWhat the pouring form asks")

found = crud.batch_for_pump(PUMP, RESIN_B)
check(found.get("reactor_name") == VESSEL,
      "the form finds the filling behind a station and resin")
check(crud.batch_for_pump(PUMP, "Resin Nobody Has") == {},
      "and gets nothing when no vessel matches, rather than a wrong one")

# ------------------------------------------------------- an unknown start --
print("\nA filling with no start time")
wipe()

s = ScopedSession()
s.add(ReactorBatch(reactor_name=VESSEL, resin_type=RESIN_A, filled_at=None))
s.commit(); s.close()
live = crud.current_batch(VESSEL)
check(live.get("hours_in_reactor") is None,
      "reads as unknown rather than as zero hours old")
check(live.get("open") is True, "and is still an open filling")

# ------------------------------------------------------------- the ability --
print("\nWho may record it")

check("manage_qc" in crud.ABILITIES, "recording QC is an ability of its own")
check("manage_qc" in crud.role_abilities("manager"), "a manager has it")
check("manage_qc" not in crud.role_abilities("operator"),
      "an operator does not, until somebody gives it to them")

bh_src = (ROOT / "api" / "routers" / "batch_history.py").read_text(encoding="utf-8")
check('"manage_qc"' in bh_src, "the batch history API asks for it before recording QC")
bh_page = (ROOT / "frontend" / "src" / "batchHistory" / "BatchHistoryPage.tsx").read_text(encoding="utf-8")
check("can_manage_qc" in bh_page, "and the QC entry form is gated on the same flag in the UI")
pouring_src = (ROOT / "api" / "routers" / "pouring.py").read_text(encoding="utf-8")
check("current_batch" in pouring_src or "batch[" in pouring_src or "BatchInfo" in pouring_src,
      "the pouring endpoint reads the batch behind the tank")
check("HTTPException" not in pouring_src.split("qc_result")[0][-400:],
      "and a failed QC does not stop the operator logging")

wipe()
print(f"\n{COUNT - len(FAILURES)}/{COUNT} passed")
if FAILURES:
    print(f"\n{len(FAILURES)} FAILED:")
    for f in FAILURES:
        print(f"  - {f}")
sys.exit(1 if FAILURES else 0)
