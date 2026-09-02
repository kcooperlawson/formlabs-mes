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
      any("Log Hourly Pouring" in "".join(t.label or "" for t in at.tabs) for _ in [0]), False)
print(f"  locked render OK  ({len(at.selectbox)} selectboxes, {len(at.button)} buttons)")

# --- B. clear the checklist for that station, page unlocks ----------------
# Pin to the station the workflow test built a real V1 run on, so the gate
# has a genuine lot to check against.
STATION, CART, RESIN = "Pump 1", "V1 (1L Cartridge)", "Draft Grey V5"
runs = crud.get_assigned_runs_df()
row = runs[runs["pump_station"] == STATION]
GOOD_LOT = str(row["lot_number"].iloc[0])
submit_daily_checklist(OP, "Shift 1", STATION)

at = run_as(OP, h_pump=STATION)
check("page still renders", at.exception, [])
check("checklist cleared -> terminal unlocks", "TERMINAL LOCKED" not in texts(at), True)
check("logging tabs now present",
      any("Log Hourly Pouring" in (t.label or "") for t in at.tabs), True)
at.selectbox(key="h_cart").set_value(CART).run()
at.selectbox(key="h_resin").set_value(RESIN).run()
print(f"  unlocked render OK ({len(at.tabs)} tabs, {STATION} / {CART} / lot {GOOD_LOT})")

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
check("stop screen asks for the stamp photo", "Photograph the stamp" in body, True)
check("photo is listed as outstanding", "photograph the stamp" in body, True)
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
check("a clean check never asks for a photo", "Photograph the stamp" not in b2, True)
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

# --- F. RPS bypasses the gate entirely -----------------------------------
at4 = run_as(OP, h_pump=STATION)
at4.selectbox(key="h_cart").set_value("RPS (5L Bulk Jug)").run()
b3 = texts(at4)
check("RPS says no label to check", "carry no lot label" in b3, True)
check("RPS restores the free-entry lot field",
      any(i.label == "Batch Lot Number" for i in at4.text_input), True)
check("RPS has no L- field", any(i.label.startswith("L-") for i in at4.text_input), False)
check("RPS submit is enabled",
      getattr([b for b in at4.button if "SUBMIT POURING LOG" in b.label][0], "disabled", None), False)
print("  RPS bypass OK")

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

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} UI checks FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} UI ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
