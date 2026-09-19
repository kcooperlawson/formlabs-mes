"""The daily pre-shift gate, ported from pages/operator_form/checklist.py's
render_checklist_gate() onto api/routers/checklist.py. Checks the same
rules the Streamlit version enforced (checklist requires today's
cleanliness photo first; both manual boxes required) plus the one
deliberate hardening: cleanliness-done-today is a real server-side query
now (cleanliness_audits), not a browser cookie, so /submit can trust it
instead of trusting whatever the client last rendered.
"""
import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import api.main  # noqa: E402
import crud  # noqa: E402

FAILS, CHECKS = [], 0


def check(cond, label):
    global CHECKS
    CHECKS += 1
    if not cond:
        FAILS.append(label)
        print(f"  FAIL  {label}")


client = TestClient(api.main.app)
CSRF = {"x-mes-client": "1"}
STATION = "New Pump #1"
SHIFT = "Shift 1"


def checklist_status(station, shift):
    return client.get("/api/checklist/status", params={"station": station, "shift": shift})


def vessel_options(station):
    return client.get("/api/checklist/vessel-options", params={"station": station})

print("=" * 66)
print("API CHECKLIST: the pre-shift gate")
print("=" * 66)

r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in for the checklist checks (got {r.status_code})")

# --- status starts false on a clean day ------------------------------------
r = checklist_status(STATION, SHIFT)
check(r.status_code == 200, f"checklist status loads (got {r.status_code})")
body = r.json()
check(body == {"checklist_done": False, "cleanliness_done_today": False},
      f"a fresh operator/station/shift starts fully ungated (got {body})")

# --- vessel-options: no vessel on this pump yet -----------------------------
r = vessel_options(STATION)
check(r.status_code == 200, f"vessel-options loads (got {r.status_code})")
check(r.json() == {"has_vessel": False, "options": []},
      "no reactors exist yet, so nothing to link and no vessel already there")

crud.add_reactor(reactor_name="Tank A", max_capacity_l=200, asset_tag="TK-A")
r = vessel_options(STATION)
check(r.json()["has_vessel"] is False, "an unlinked reactor still means has_vessel=False for this pump")
check(any(o["value"] == "Tank A" for o in r.json()["options"]),
      "...but it now shows up as something that CAN be linked")
check(any("(TK-A)" in o["label"] for o in r.json()["options"]),
      "...labelled the same way shared._vessel_label formats it, asset tag included")

crud.link_vessel_to_pump("Tank A", STATION)
r = vessel_options(STATION)
check(r.json() == {"has_vessel": True, "options": []},
      "once linked, the question isn't asked again for this pump")

# --- the checklist cannot be submitted before the cleanliness photo --------
r = client.post("/api/checklist/submit", json={
    "station": STATION, "shift": SHIFT, "qr_checked": True, "materials_checked": True,
}, headers=CSRF)
check(r.status_code == 400, f"submit is refused before the cleanliness photo (got {r.status_code})")
check("Cleanliness" in r.json().get("detail", ""), "...and says which step is missing")

# --- both manual boxes are required, independent of the photo --------------
r = client.post("/api/checklist/cleanliness", data={"station": STATION, "shift": SHIFT, "notes": "Clean."},
                 files=[("photos", ("photo1.jpg", io.BytesIO(b"fake-jpeg-bytes"), "image/jpeg"))],
                 headers=CSRF)
check(r.status_code == 200, f"the cleanliness photo submits (got {r.status_code}, {r.text[:200]})")

r = client.post("/api/checklist/submit", json={
    "station": STATION, "shift": SHIFT, "qr_checked": True, "materials_checked": False,
}, headers=CSRF)
check(r.status_code == 400, f"submit still refused with only one manual box checked (got {r.status_code})")

# --- a photo-less cleanliness submission is refused, unless skip_photo -----
r = client.post("/api/checklist/cleanliness", data={"station": "New Pump #2", "shift": SHIFT},
                 headers=CSRF)
check(r.status_code == 400, f"a cleanliness submission with no photo is refused (got {r.status_code})")

r = client.post("/api/checklist/cleanliness",
                 data={"station": "New Pump #2", "shift": SHIFT, "notes": "Clean, nothing to show.", "skip_photo": "true"},
                 headers=CSRF)
check(r.status_code == 200, f"...but checking skip_photo lets a clean station through with no photo (got {r.status_code}, {r.text[:200]})")
r = checklist_status("New Pump #2", SHIFT)
check(r.json()["cleanliness_done_today"] is True, "...and it counts as today's cleanliness check, same as a photo would")

# --- now the full submit succeeds, and links the vessel on the way through -
r = client.post("/api/checklist/submit", json={
    "station": STATION, "shift": SHIFT, "qr_checked": True, "materials_checked": True,
    "vessel_reactor_name": "Tank A",
}, headers=CSRF)
check(r.status_code == 200, f"submit succeeds once every step is done (got {r.status_code}, {r.text[:200]})")

r = checklist_status(STATION, SHIFT)
check(r.json() == {"checklist_done": True, "cleanliness_done_today": True},
      f"status now reflects the completed checklist (got {r.json()})")

# --- a different station on the same shift needs its own checklist ---------
r = checklist_status("New Pump #2", SHIFT)
check(r.json()["checklist_done"] is False,
      "the checklist is scoped per station - a second pump isn't covered by the first")

# --- the "mark already done" override --------------------------------------
r = client.post("/api/checklist/mark-already-done",
                 json={"station": "Old Pump/Other", "shift": SHIFT, "already_who": "Maria"}, headers=CSRF)
check(r.status_code == 200, f"the temporary override unlocks the terminal (got {r.status_code})")
r = checklist_status("Old Pump/Other", SHIFT)
check(r.json() == {"checklist_done": True, "cleanliness_done_today": True},
      "the override satisfies both flags at once, same as a real submit")

r = client.post("/api/checklist/mark-already-done",
                 json={"station": "New Pump #2", "shift": SHIFT, "already_who": "  "}, headers=CSRF)
check(r.status_code == 400, f"the override requires an actual name (got {r.status_code})")

# --- everything here requires a session -------------------------------------
# --- who has done their checks, and for any day ----------------------------
# Built from rows the floor already produces, so it reports what happened
# rather than what somebody remembered to tick.
from datetime import date as _date, timedelta as _timedelta  # noqa: E402

import crud  # noqa: E402

TODAY = _date.today().isoformat()
r = client.get(f"/api/checklist/compliance?on_date={TODAY}")
check(r.status_code == 200, f"the compliance view answers (got {r.status_code})")
body = r.json()
check(body["date"] == TODAY, f"...for the day asked for (got {body['date']})")
check(body["scope"] == "self", f"an operator sees their own row only (got {body['scope']})")

crud.add_hourly_log(operator_name="Demo Operator", pump_station="New Pump #1", shift="Shift 1",
                    cartridge_type="V2", resin_type="Grey", lot_number="LOT-C1",
                    bottles=30, scrap_empty=0, scrap_filled=0)
rows = client.get(f"/api/checklist/compliance?on_date={TODAY}").json()["rows"]
mine = [row for row in rows if row["pump_station"] == "New Pump #1"]
check(len(mine) == 1, f"a pump that was poured on appears (got {[r['pump_station'] for r in rows]})")
# This operator did their startup checklist and start-of-shift photo earlier
# in this file, so those read as done and the end-of-shift one is what's
# still outstanding - which is the distinction the screen exists to make.
check(mine[0]["checklist_at"] and mine[0]["start_audit_at"],
      f"...with the checks they did already on record (got {mine[0]})")
check(mine[0]["end_expected"] is True and mine[0]["end_audit_at"] is None,
      f"...the end-of-shift check is expected on their last pump and not done yet (got {mine[0]})")
check(mine[0]["complete"] is False,
      "...so the row is not complete, which is the thing worth chasing before they leave")
check(mine[0]["poured"] >= 1, "...showing it was actually poured on, which is what makes it worth chasing")

# Moving to a second pump later in the shift: that pump wants a transfer
# check, NOT a second start-of-shift photo. Demanding one would mark a
# correctly run shift as incomplete, and a column that cries wolf gets
# ignored by everybody.
check(mine[0]["start_expected"] is True,
      f"the pump a shift began on does want its start-of-shift photo (got {mine[0]})")
crud.add_hourly_log(operator_name="Demo Operator", pump_station="Moved-To Pump", shift="Shift 1",
                    cartridge_type="V2", resin_type="Grey", lot_number="LOT-C2",
                    bottles=30, scrap_empty=0, scrap_filled=0)
rows = client.get(f"/api/checklist/compliance?on_date={TODAY}").json()["rows"]
moved = [row for row in rows if row["pump_station"] == "Moved-To Pump"]
check(len(moved) == 1, f"the pump they moved to appears too (got {[r['pump_station'] for r in rows]})")
check(moved[0]["transfer_expected"] is True and moved[0]["start_expected"] is False,
      f"...wanting a transfer check instead of a second start-of-shift photo (got {moved[0]})")
first = [row for row in rows if row["pump_station"] == "New Pump #1"][0]
check(first["end_expected"] is False and moved[0]["end_expected"] is True,
      f"...and the end-of-shift photo moves with them to the last pump worked (got {first}, {moved[0]})")

old_day = (_date.today() - _timedelta(days=9)).isoformat()
history = client.get(f"/api/checklist/compliance?on_date={old_day}")
check(history.status_code == 200 and history.json()["date"] == old_day,
      f"any past day can be asked for, which is what makes this a history (got {history.status_code})")

bad = client.get("/api/checklist/compliance?on_date=last-tuesday")
check(bad.status_code == 400, f"a date that isn't one is refused plainly (got {bad.status_code})")

# Management sees the whole floor from the same endpoint - and standing in
# for one operator narrows it back to that operator, so the card on their
# form shows what they would see rather than a plant-wide table.
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
boss = client.get(f"/api/checklist/compliance?on_date={TODAY}").json()
check(boss["scope"] == "everyone", f"a manager sees everyone (got {boss['scope']})")
check(len(boss["rows"]) >= len(rows), "...which is at least what one operator could see")
stand_in = client.get(
    f"/api/checklist/compliance?on_date={TODAY}&as_operator=Demo+Operator").json()
check(stand_in["scope"] == "self", f"standing in for an operator narrows it (got {stand_in['scope']})")
check(stand_in["rows"] and all(r["operator_name"] == "Demo Operator" for r in stand_in["rows"]),
      f"...to that operator's rows only (got {[r['operator_name'] for r in stand_in['rows']]})")
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)

client.post("/api/auth/logout", headers=CSRF)
r = checklist_status(STATION, SHIFT)
check(r.status_code == 401, f"checklist status refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API CHECKLIST CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API CHECKLIST ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
