"""Headless render of the real Operator_Form.py with Streamlit's AppTest.

This executes the page script the way a browser session would - widgets,
branches, session state - against the same Postgres the workflow test filled.
"""
import os, sys, warnings
warnings.filterwarnings("ignore")
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _boot import boot, ROOT
srv, uri = boot(fresh=False)

from streamlit.testing.v1 import AppTest
import streamlit as _st

# AppTest runs one script with no multipage registry behind it, so the
# cross-page navigation calls have nothing to resolve against. Stub the three
# that need that registry - they are chrome, not behaviour under test.
_st.page_link = lambda *a, **k: None
_st.logo = lambda *a, **k: None
_st.switch_page = lambda *a, **k: None
import crud
from crud import submit_daily_checklist, has_completed_daily_checklist, create_user

FAILS, CHECKS = [], 0
def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  ✗ {label}\n      got:      {got!r}\n      expected: {exp!r}")

def texts(at):
    """Every bit of rendered text on the page, flattened."""
    out = []
    for group in (at.error, at.warning, at.info, at.success, at.markdown, at.caption):
        for e in group:
            out.append(str(e.value))
    return "\n".join(out)

def run_as(name, role="operator", shift="Shift 1", **state):
    at = AppTest.from_file(str(ROOT / "pages" / "Operator_Form.py"), default_timeout=90)
    at.session_state["authenticated"] = True
    at.session_state["user_name"] = name
    at.session_state["user_role"] = role
    at.session_state["user_shift"] = shift
    at.session_state["user_id"] = 1
    at.session_state["username"] = name.split()[0].lower()
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    return at

print("=" * 66)
print("UI RENDER: pages/Operator_Form.py")
print("=" * 66)

# Most of this file is about the lot gate comparing a typed code against the
# lot on an open run, so this plant has to be one that dispatches runs. A new
# install is not - see migration 0009 - and with work orders off the page
# deliberately cannot see a run at all, which would fail every gate assertion
# below for the right reason and the wrong purpose. Simple mode gets its own
# section at the end, where it is the thing under test rather than the setup.
import database as _db_setup
_db_setup.update_plant_settings({"simple_mode": False})

# --- A. an operator who has NOT done the checklist sees the lock -----------
import uuid
OP = "Dee " + uuid.uuid4().hex[:6].upper()
create_user(OP.split()[1].lower(), f"{OP.split()[1].lower()}@x.com", "5555", OP, "operator")
at = run_as(OP)
check("page renders without raising", at.exception, [])
body = texts(at)
check("locked operator sees the terminal lock", "TERMINAL LOCKED" in body, True)
check("lock screen names the station", "Pump" in body, True)
check("lock screen offers a pump picker",
      any(sb.label.startswith("📍 Which pump") for sb in at.selectbox), True)
check("no logging tabs while locked",
      any("Pouring" in "".join(t.label or "" for t in at.tabs) for _ in [0]), False)
print(f"  locked render OK  ({len(at.selectbox)} selectboxes, {len(at.button)} buttons)")

# --- B. clear the checklist for that station, page unlocks ----------------
# Pin to the station the workflow test built a real V1 run on, so the gate
# has a genuine lot to check against.
STATION, CART, RESIN = "Pump 1", "V1 (1L Cartridge)", "Draft Grey V5"
runs = crud.get_assigned_runs_df()
row = runs[runs["pump_station"] == STATION]
GOOD_LOT = str(row["lot_number"].iloc[0])

# That run has to still be OPEN, or the gate has no lot to check against and
# every assertion below fails for a reason that has nothing to do with the
# gate. The database these suites share keeps its rows between runs, so the
# logs pile up until the run completes itself - which took a few weeks of
# running the suite, and then looked exactly like the lot check had broken.
# Reopening it here costs nothing and makes the file say what it needs.
if str(row["status"].iloc[0]).lower() != "active" or \
        int(row["current_units"].iloc[0]) >= int(row["target_units"].iloc[0]):
    from db_core import ScopedSession as _S
    from models import AssignedRun as _R
    _s = _S()
    _run = _s.query(_R).filter(_R.id == int(row["id"].iloc[0])).first()
    if _run is not None:
        _run.status, _run.current_units = "Active", 0
        _run.target_units = max(int(_run.target_units or 0), 100000)
        _s.commit()
    _s.close()
    crud.get_assigned_runs_df.clear() if hasattr(crud.get_assigned_runs_df, "clear") else None
    runs = crud.get_assigned_runs_df()
    row = runs[runs["pump_station"] == STATION]
submit_daily_checklist(OP, "Shift 1", STATION)

at = run_as(OP, h_pump=STATION)
check("page still renders", at.exception, [])
check("checklist cleared -> terminal unlocks", "TERMINAL LOCKED" not in texts(at), True)
check("logging tabs now present",
      any("Pouring" in (t.label or "") for t in at.tabs), True)
at.selectbox(key="h_cart").set_value(CART).run()
at.selectbox(key="h_resin").set_value(RESIN).run()
print(f"  unlocked render OK ({len(at.tabs)} tabs, {STATION} / {CART} / lot {GOOD_LOT})")

# --- the vessel this pour comes off ---------------------------------------
# Reported on the first day of real use: "there is no reactor selector so it
# has no idea what reactor I am pouring from." Nobody picks it - it is derived
# from the station and the resin, the same way the level arithmetic derives it
# - but a derived link nobody can see is one nobody can tell is wrong. So the
# form says which tank it thinks this is, or says plainly that there is none.
#
# Both directions are checked against a vessel this test creates, not against
# whatever the shared fixture happens to be carrying. The first version of
# this check passed or failed depending on whether it had been run before.
from crud import (add_reactor as _add_reactor,  # noqa: E402
                  update_reactor_config as _link_reactor,
                  get_all_reactors_df as _reactors_df)

_existing = _reactors_df()
if _existing.empty or "UI Vessel" not in set(_existing["reactor_name"]):
    _add_reactor("UI Vessel", 5000)
    _existing = _reactors_df()
_rid = int(_existing[_existing["reactor_name"] == "UI Vessel"]["id"].iloc[0])
_link_reactor(_rid, RESIN, STATION)

at_v = run_as(OP, h_pump=STATION)
at_v.selectbox(key="h_cart").set_value(CART).run()
at_v.selectbox(key="h_resin").set_value(RESIN).run()
check("the form names the vessel this pour comes off", "UI Vessel" in texts(at_v), True)
check("and does not warn when there is one", "No vessel is linked" in texts(at_v), False)

# Now break the link and look again. Same station, same form, nothing else
# changed - so a warning here can only be about the vessel.
_link_reactor(_rid, "", "")
at_n = run_as(OP, h_pump=STATION)
at_n.selectbox(key="h_cart").set_value(CART).run()
at_n.selectbox(key="h_resin").set_value(RESIN).run()
check("with nothing linked the form says so rather than staying quiet",
      "No vessel is linked" in texts(at_n), True)
check("and it does not stop the operator logging",
      at_n.exception, [])
_link_reactor(_rid, RESIN, STATION)
print("  the vessel line OK")

# --- the form opens where the operator left it -----------------------------
# Twelve logs a shift, and the station, the format and the resin are the same
# every time. Remembered on the account rather than in the browser, because a
# phone locking or a session dropping is the normal case on a floor.
from crud import get_last_picks as _picks, save_last_picks as _save  # noqa: E402

_save(OP, STATION, CART, RESIN)
check("what the operator last logged is remembered against the account",
      _picks(OP), {"station": STATION, "cartridge": CART, "resin": RESIN})

at_s = run_as(OP)
check("and the form opens on it instead of asking again",
      at_s.selectbox(key="h_pump").value, STATION)
check("including the container format", at_s.selectbox(key="h_cart").value, CART)
check("and the resin", at_s.selectbox(key="h_resin").value, RESIN)
check("the page still renders clean with all three pre-filled", at_s.exception, [])
print("  remembered picks OK")

# --- C. the lot gate, nothing typed yet -----------------------------------
def gate(at):
    return {"lot_field": any(i.label.startswith("L-") for i in at.text_input),
            "body": texts(at)}

check("gate renders a lot field", gate(at)["lot_field"], True)
check("expected lot is masked, never printed", GOOD_LOT not in gate(at)["body"], True)
check("mask is shown instead", "• • • • • • • • •" in gate(at)["body"], True)
submit = [b for b in at.button if "SUBMIT POURING LOG" in b.label]
check("submit button exists", len(submit), 1)
check("submit is disabled before the check", getattr(submit[0], "disabled", None), True)
check("page says what is missing", "Before you can submit" in gate(at)["body"], True)
print("  gate blocks an untouched form OK")

# --- D. type the WRONG lot -> STOP screen + reason widgets ----------------
at.text_input(key="h_lot_entered").set_value("L-9999XXXX").run()
body = texts(at)
check("wrong lot triggers the stop screen", "STOP" in body and "DO NOT POUR" in body, True)
check("stop screen asks for a reason",
      any((sb.label or "").startswith("Logging it anyway") for sb in at.selectbox), True)
check("stop screen offers the pull-the-cartridge button",
      any("pulled it" in b.label for b in at.button), True)
check("stop screen asks for the photo", "Photograph the cartridge bottom" in body, True)
check("the cartridge instruction points at the same label",
      "lot label on the bottom" in body, True)
check("photo is listed as outstanding", "photograph the cartridge bottom" in body, True)
check("submit still disabled on a mismatch",
      getattr([b for b in at.button if "SUBMIT POURING LOG" in b.label][0], "disabled", None), True)
check("expected lot stays masked even on the stop screen", GOOD_LOT not in body, True)
print("  mismatch path OK")

# --- E. type the RIGHT lot -> green, only the photo outstanding -----------
at2 = run_as(OP, h_pump=STATION)
at2.selectbox(key="h_cart").set_value(CART).run()
at2.selectbox(key="h_resin").set_value(RESIN).run()
at2.text_input(key="h_lot_entered").set_value(f"L-{GOOD_LOT}").run()
b2 = texts(at2)
check("matching lot goes green", "Lot matches this run" in b2, True)
check("nothing left blocking submit", "Before you can submit" not in b2, True)
check("a clean check never asks for a photo", "Photograph the" not in b2, True)
check("no stop screen on a match", "DO NOT POUR" not in b2, True)
check("a clean check unlocks submit",
      getattr([b for b in at2.button if "SUBMIT POURING LOG" in b.label][0], "disabled", None), False)

# messy transcription of the same lot must still match
at3 = run_as(OP, h_pump=STATION)
at3.selectbox(key="h_cart").set_value(CART).run()
at3.selectbox(key="h_resin").set_value(RESIN).run()
at3.text_input(key="h_lot_entered").set_value(f"  l- {GOOD_LOT.lower()}  ").run()
check("messy transcription still matches", "Lot matches this run" in texts(at3), True)
print(f"  match path OK (lot {GOOD_LOT}, incl. messy transcription)")

# --- F. RPS is gated too, and the wording follows the container ----------
# The jugs were excluded on the understanding that they carried no label. They
# always have, and the plant now requires the tag to be on before pouring, so
# the check applies. Asserted on the rendered form rather than on a constant,
# because the thing that changed is what an operator is shown.
at4 = run_as(OP, h_pump=STATION)
at4.selectbox(key="h_cart").set_value("RPS (5L Bulk Jug)").run()
b3 = texts(at4)
check("RPS no longer claims there is nothing to check", "carry no lot label" in b3, False)
check("RPS gets the free-entry field taken away",
      any(i.label == "Batch Lot Number" for i in at4.text_input), False)
check("RPS gets a lot field to read into",
      any(i.label.startswith("L-") for i in at4.text_input), True)
# The words follow the container, and only the noun differs: both carry the
# same kind of lot label in the same place, on the bottom of the empty. An
# operator at the pump is the only person who would notice the screen getting
# that wrong, which is why it is asserted here rather than trusted.
check("the instruction says to turn the JUG over", "Turn the jug over" in b3, True)
check("and points at the lot label on its bottom",
      "lot label on the bottom" in b3, True)
check("and does not tell them to turn a cartridge over",
      "Turn the cartridge over" in b3, False)
check("the section heading names the jug too", "Jug Lot Verification" in b3, True)
check("RPS submit is blocked until the tag is read",
      getattr([b for b in at4.button if "SUBMIT POURING LOG" in b.label][0], "disabled", None), True)

# The same gate, both directions, on a jug.
_rps_runs = crud.get_assigned_runs_df()
_rps_row = _rps_runs[_rps_runs["cartridge_type"].astype(str).str.upper().str.startswith("RPS")]
if not _rps_row.empty:
    RPS_STATION = str(_rps_row["pump_station"].iloc[0])
    RPS_RESIN = str(_rps_row["resin_type"].iloc[0])
    RPS_LOT = str(_rps_row["lot_number"].iloc[0])
    submit_daily_checklist(OP, "Shift 1", RPS_STATION)

    at5 = run_as(OP, h_pump=RPS_STATION)
    at5.selectbox(key="h_cart").set_value("RPS (5L Bulk Jug)").run()
    at5.selectbox(key="h_resin").set_value(RPS_RESIN).run()
    at5.text_input(key="h_lot_entered").set_value("L-0000WRONG").run()
    b4 = texts(at5)
    check("a wrong tag on a jug stops the pour", "DO NOT POUR" in b4, True)
    check("and the stop screen says jug, not cartridge", "This jug is not from the lot" in b4, True)
    check("the expected lot is masked on a jug too", RPS_LOT not in b4, True)
    check("and the masking hint names the jug", "read the jug, not the screen" in b4, True)

    at6 = run_as(OP, h_pump=RPS_STATION)
    at6.selectbox(key="h_cart").set_value("RPS (5L Bulk Jug)").run()
    at6.selectbox(key="h_resin").set_value(RPS_RESIN).run()
    at6.text_input(key="h_lot_entered").set_value(f"L-{RPS_LOT}").run()
    check("the right tag clears the gate on a jug",
          "Lot matches this run" in texts(at6), True)
    print(f"  RPS gate OK ({RPS_STATION} / {RPS_RESIN}, lot {RPS_LOT})")
else:
    check(False, "no RPS run on file to exercise the jug gate against")

# --- F2. the wording tracks the picker, within one session ---------------
# It would be easy for this to be right on a page that opens as RPS and wrong
# the moment somebody switches format without reloading, because the strings
# are chosen once per render. Switch it back and forth on the same instance
# and read what the page says each time.
at_sw = run_as(OP, h_pump=STATION)
at_sw.selectbox(key="h_cart").set_value("RPS (5L Bulk Jug)").run()
sw_rps = texts(at_sw)
at_sw.selectbox(key="h_cart").set_value("V1 (1L Cartridge)").run()
sw_v1 = texts(at_sw)
at_sw.selectbox(key="h_cart").set_value("RPS (5L Bulk Jug)").run()
sw_back = texts(at_sw)

check("picking RPS says jug", "Turn the jug over" in sw_rps, True)
check("switching to V1 says cartridge again", "Turn the cartridge over" in sw_v1, True)
check("and stops saying jug", "Turn the jug over" in sw_v1, False)
check("switching back to RPS says jug again", "Turn the jug over" in sw_back, True)
check("the heading follows too (V1)", "Cartridge Lot Verification" in sw_v1, True)
check("the heading follows too (RPS)", "Jug Lot Verification" in sw_back, True)
print("  wording follows the Container Format picker, not the page")

# --- G. the pump form link, on the real page -----------------------------
# Asserted against the rendered page rather than against normalise() alone,
# because the thing that matters is whether an operator gets a button - and a
# correct URL that never reaches st.link_button is the same to them as no
# button at all. Both directions: configured shows it, cleared removes it.
def _links(at):
    """(label, url) for every link_button on the page.

    AppTest has no typed accessor for link_button - it arrives as an
    UnknownElement whose .value raises - so read the protobuf, which carries
    both the wording the operator sees and the address they would be sent to.
    """
    out = []
    for e in at.get("link_button"):
        out.append((getattr(e.proto, "label", ""), getattr(e.proto, "url", "")))
    return out

# Written through database.py rather than crud.py on purpose: the page reads
# settings through a cached wrapper, and only the database-module writer drops
# that cache. Going straight to crud here would leave the page reading a stale
# copy and the test would be asserting against the wrong thing.
import database as _db
_saved = crud.get_plant_settings()
try:
    _db.update_plant_settings({"pump_form_url": "https://forms.example.com/pump-check",
                                "pump_form_label": "Pump check"})
    at5 = run_as(OP, h_pump=STATION)
    links = _links(at5)
    check("a configured pump form renders a button",
          any("Pump check" in lbl for lbl, _ in links), True)
    check("pointing at the address that was configured",
          any(url == "https://forms.example.com/pump-check" for _, url in links), True)

    # The screen that actually needs it. The checklist's first box asks the
    # operator to have filled the form in, and the checklist is the LOCKED
    # screen - nothing below its st.stop() renders until it clears. The button
    # was first placed above the logging tabs, which an operator at the
    # checklist cannot reach, so a configured address looked like it did
    # nothing. An operator who has not cleared today's checklist is the case.
    LOCKED = "Lee " + uuid.uuid4().hex[:6].upper()
    create_user(LOCKED.split()[1].lower(), f"{LOCKED.split()[1].lower()}@x.com", "5555",
                LOCKED, "operator")
    at_lock = run_as(LOCKED)
    check("the locked checklist screen is the one being tested",
          "TERMINAL LOCKED" in texts(at_lock), True)
    lock_links = _links(at_lock)
    check("the pump form button is on the locked checklist screen",
          any("Pump check" in lbl for lbl, _ in lock_links), True)
    check("and points at the configured address there too",
          any(url == "https://forms.example.com/pump-check" for _, url in lock_links), True)

    # An address typed without a scheme is the most common real paste. It must
    # not reach the page scheme-relative, or the browser resolves it against
    # the MES and the button lands on a 404 that looks like the MES is broken.
    _db.update_plant_settings({"pump_form_url": "forms.example.com/pump-check"})
    at6 = run_as(OP, h_pump=STATION)
    check("a scheme-less address still renders a button", bool(_links(at6)), True)
    check("and is sent out as https, not resolved against the MES",
          all(url.startswith("https://") for _, url in _links(at6)), True)

    _db.update_plant_settings({"pump_form_url": "", "pump_form_label": ""})
    at7 = run_as(OP, h_pump=STATION)
    check("no configured form means no button at all", _links(at7), [])
    check("and no warning aimed at an operator who could not act on it",
          "pump form address" in texts(at7), False)
    print("  pump form link OK (shown when set, absent when not)")
finally:
    _db.update_plant_settings({"pump_form_url": _saved.get("pump_form_url", ""),
                                "pump_form_label": _saved.get("pump_form_label", "")})


# --- G. simple mode: a plant that logs and does not dispatch --------------
# The default for a new install. The point of this section is that the page
# stops describing what is missing: no run cards, no notice about a run that
# did not match, and - the one that matters for safety rather than tone - no
# comparison against a run the operator was never shown.
try:
    _db.update_plant_settings({"simple_mode": True})
    at8 = run_as(OP, h_pump=STATION)
    body8 = texts(at8)

    check("page still renders with work orders off", at8.exception, [])
    check("no run cards headed by a manager's name",
          "Active Assigned Production Runs" in body8, False)
    check("no notice about a run that did not match",
          "No open run matches" in body8, False)
    check("nothing sends the operator to find a manager",
          "Plant Manager" in body8, False)
    check("and no leftover 'no production runs in database'",
          "No production runs" in body8, False)
    check("focus mode is not offered when it could only show an empty screen",
          any("Focus mode" in (t.label or "") for t in at8.toggle), False)

    # The lot field is still there, and still asks for the same thing. This is
    # the part that has to survive: recording which lot went into a pour is
    # the whole traceability answer, and it needs nothing set up.
    check("the lot field is still asked for",
          any("lot on the" in (ti.label or "") for ti in at8.text_input), True)
    check("and the instruction still points at the label on the bottom",
          "lot label on the bottom" in body8, True)

    # A stale open run must not reach a terminal that cannot display it. The
    # workflow fixture leaves a real V1 run on this station with a real lot;
    # with work orders off, typing a WRONG code must not raise a stop screen
    # for a run the operator has no way to know about.
    for ti in at8.text_input:
        if "lot on the" in (ti.label or ""):
            ti.set_value("L-0000WRONG").run()
            break
    body8b = texts(at8)
    check("a hidden run cannot stop a pour it was never shown for",
          "DO NOT POUR" in body8b, False)
    check("the wrong-looking code is simply recorded",
          "Recorded" in body8b or "recorded" in body8b, True)
    print("  simple mode OK (logs, records the lot, invents no missing setup)")
finally:
    _db.update_plant_settings({"simple_mode": False})

# --- H. a pour that is an amount rather than a count ---------------------
# The arithmetic has its own file. What is asserted here is the part only the
# real page can answer: that the option is absent until the plant switches it
# on, that switching it on does not disturb the formats that were already
# there, and that an amount which cannot be true actually stops the submit
# rather than merely printing something red above an enabled button.
try:
    _db.update_plant_settings({"enable_bulk_pour": False})
    at_off = run_as(OP, h_pump=STATION)
    _opts_off = list(at_off.selectbox(key="h_cart").options)
    check("a plant that has not switched it on sees no bulk option",
          any("measured amount" in o for o in _opts_off), False)
    check("and sees the four formats it always saw", len(_opts_off), 4)

    _db.update_plant_settings({"enable_bulk_pour": True})
    at_on = run_as(OP, h_pump=STATION)
    _opts_on = list(at_on.selectbox(key="h_cart").options)
    check("switching it on adds the option",
          any("measured amount" in o for o in _opts_on), True)
    # The name it was given first said "Drum / Tote", which is one of the
    # things it is for and reads as an exclusion of everything else. The
    # operator who needed it was filling unlabelled bottles off a drum.
    check("and the option does not name one container type",
          any(o.startswith("Drum") for o in _opts_on), False)
    check("and moves none of the ones already there", _opts_on[:4], _opts_off)

    # The trap this section exists for: "RPS (5L Bulk Jug)" contains the word
    # "Bulk". A format picked by substring turned every 5-litre jug into a
    # measured pour the moment a bulk option was added, and the only visible
    # symptom was a lot check that quietly stopped applying to jugs.
    at_on.selectbox(key="h_cart").set_value("RPS (5L Bulk Jug)").run()
    check("a jug is still a jug once a bulk option exists",
          "Jug Lot Verification" in texts(at_on), True)
    check("and still asks for its lot", "Turn the jug over" in texts(at_on), True)

    _tank = _db.get_all_reactors_df()
    if not _tank.empty:
        _row = _tank.iloc[0]
        _resin, _pump = str(_row["current_resin"]), str(_row["assigned_pump"])
        _cap = float(_row["max_capacity_l"])
        submit_daily_checklist(OP, "Shift 1", _pump)

        at_b = run_as(OP, h_pump=_pump)
        at_b.selectbox(key="h_cart").set_value("Other container (measured amount)").run()
        at_b.selectbox(key="h_resin").set_value(_resin).run()

        # The count field is replaced by an amount field, not added to.
        check("a bulk pour asks for an amount",
              any(n.key == "h_bulk_each" for n in at_b.number_input), True)
        check("and stops asking for a container count in the big field",
              any(n.key == "h_filled" for n in at_b.number_input), False)

        at_b.number_input(key="h_bulk_each").set_value(180.0).run()
        _sub = [b for b in at_b.button if "SUBMIT POURING LOG" in b.label][0]
        check("an ordinary amount can be submitted", _sub.disabled, False)
        check("and the litres are stated before the submit",
              any("off this vessel" in str(m.value) for m in at_b.markdown), True)

        # 1800 typed instead of 180 is the failure this catches. It looks
        # entirely ordinary in a number box and shows up an hour later as an
        # empty vessel on the wall display.
        # Just over this tank's capacity, deliberately - far enough over to be
        # impossible, close enough that it does not trip the "larger than any
        # vessel on the floor" rule instead and pass for the wrong reason.
        at_b.number_input(key="h_bulk_each").set_value(_cap + 400).run()
        _sub = [b for b in at_b.button if "SUBMIT POURING LOG" in b.label][0]
        check("more than the vessel holds cannot be submitted", _sub.disabled, True)
        check("and the page says why rather than just greying the button",
              any("more than this vessel holds" in str(e.value) for e in at_b.error), True)
        check("naming the vessel's capacity, so it is clear which number is wrong",
              any(f"{_cap:,.0f} L" in str(e.value) for e in at_b.error), True)

        at_b.number_input(key="h_bulk_each").set_value(50000.0).run()
        _sub = [b for b in at_b.button if "SUBMIT POURING LOG" in b.label][0]
        check("and an amount larger than anything on the floor is stopped too",
              _sub.disabled, True)
        # Resin that came out of a drum rather than the tank. The vessel
        # checks are about this tank, and this pour did not come off it, so
        # an amount over the tank's capacity is not evidence of anything and
        # must not block the log. The size check stays.
        at_b.number_input(key="h_bulk_each").set_value(_cap + 400).run()
        at_b.radio(key="h_bulk_src").set_value(
            "A drum or container already off the tank").run()
        _sub = [b for b in at_b.button if "SUBMIT POURING LOG" in b.label][0]
        check("an off-tank pour is not judged against the tank's capacity",
              _sub.disabled, False)
        check("and the line stops claiming the litres came off a vessel",
              any("without moving a tank" in str(m.value) for m in at_b.markdown), True)
        check("and the tank is not named as the source",
              "Drawing from" in texts(at_b), False)

        at_b.number_input(key="h_bulk_each").set_value(50000.0).run()
        _sub = [b for b in at_b.button if "SUBMIT POURING LOG" in b.label][0]
        check("an off-tank pour is still stopped when the amount is impossible",
              _sub.disabled, True)

        print(f"  bulk pours OK ({_resin} / {_pump}, {_cap:,.0f} L vessel)")
    else:
        check(False, "no reactor on file to check a bulk pour against")
finally:
    _db.update_plant_settings({"enable_bulk_pour": False})

# --- the submit button after a log actually lands --------------------------
# Reported from the floor: on a run where the confirmation was not drawing,
# the operator kept pressing Submit and logged the same pour several times.
# Every one of those writes looked correct to the application, so nothing
# stopped them. For a few seconds after a log lands the button is not on the
# screen at all, and what stands in its place says what was recorded.
import components as _comp  # noqa: E402
import time  # noqa: E402

at_s = run_as(OP, h_pump=STATION)
at_s.selectbox(key="h_cart").set_value(CART).run()
at_s.selectbox(key="h_resin").set_value(RESIN).run()
at_s.text_input(key="h_lot_entered").set_value(f"L-{GOOD_LOT}").run()
_before = [b for b in at_s.button if "SUBMIT POURING LOG" in b.label]
check("the button is there before the log", len(_before), 1)

_before[0].click().run()
_after = texts(at_s)
check("the button is gone for a moment after the log lands",
      len([b for b in at_s.button if "SUBMIT POURING LOG" in b.label]), 0)
check("and something in its place says the log went in", "Logged" in _after, True)
check("naming what was recorded rather than saying 'saved'", RESIN in _after, True)
check("with the wait stated, so the screen does not look stuck",
      "You can submit again in" in _after, True)

# The lock is time-based, not a flag somebody has to remember to clear. Wind
# the clock back past the window and the real button is there again.
at_s.session_state["_submit_lock_pour"] = {
    "at": time.time() - (_comp.SUBMIT_LOCK_SECONDS + 1), "message": "x"}
at_s.run()
check("and it comes back once the seconds are up",
      len([b for b in at_s.button if "SUBMIT POURING LOG" in b.label]), 1)
check("with the green block gone", "You can submit again in" in texts(at_s), False)
print("  the submit lock OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} UI checks FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} UI ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
