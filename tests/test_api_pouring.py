"""The reactor-lookup endpoint and its four write actions - the one
genuinely tricky mechanic ported from pouring_tab.py (lines ~134-257):
which tank a pour will be credited to, and whether picking a resin means a
changeover, a blank tank, no vessel at all, or more than one candidate.

Every branch crud.reactor_for()/vessels_on_pump() can produce is exercised
here by seeding the exact Reactor rows that trigger it, the same way the
original Streamlit block was driven by whatever was already in the
database when the page rendered.
"""
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


def lookup(station, resin):
    return client.get("/api/pouring/reactor-lookup", params={"station": station, "resin": resin})


print("=" * 66)
print("API POURING: reactor lookup and the changeover mechanic")
print("=" * 66)

r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in for the pouring checks (got {r.status_code})")

# --- no_vessel: nothing on this pump at all ---------------------------------
r = lookup(STATION, "Standard Clear V5")
check(r.status_code == 200, f"lookup loads with nothing configured yet (got {r.status_code})")
check(r.json()["status"] == "no_vessel", f"no reactor anywhere -> no_vessel (got {r.json()})")
check(r.json()["options"] == [], "...and nothing to offer as a link target either")

# --- blank: one vessel on the pump, holding nothing yet ---------------------
crud.add_reactor(reactor_name="Tank A", max_capacity_l=200, asset_tag="TK-A", assigned_pump=STATION)
r = lookup(STATION, "Standard Clear V5")
check(r.json()["status"] == "blank", f"one empty vessel on the pump -> blank (got {r.json()})")
check(r.json()["vessel"]["reactor_name"] == "Tank A", "...naming the vessel that will adopt this resin")
check(r.json()["vessel"]["tag"] == "TK-A", "...by its asset tag, matching shared display logic")

# --- matched: the vessel already holds this resin ---------------------------
crud.record_changeover("Tank A", "Standard Clear V5", operator="Demo Operator", shift="Shift 1",
                       pump_station=STATION)
r = lookup(STATION, "Standard Clear V5")
check(r.json()["status"] == "matched", f"vessel already on this resin -> matched (got {r.json()})")
check(r.json()["vessel"]["reactor_name"] == "Tank A", "...naming the same vessel")
# record_changeover ends the old filling and opens a new one itself (crud.py:
# "A changeover is the end of one filling and the start of the next") - so a
# batch is already open here, not absent.
check(r.json()["batch"] is not None,
      "a changeover opens a new filling on its own - there IS a batch to show")
check(r.json()["batch"]["qc_result"] == "", "...with no QC result yet, since none was sent")
check(r.json()["can_mark_empty"] is True,
      "operator role is granted mark_reactor_empty by default (crud.ROLE_ABILITIES)")

# --- changeover: the vessel holds something else ----------------------------
r = lookup(STATION, "Draft Grey V5")
check(r.json()["status"] == "changeover", f"vessel on a different resin -> changeover (got {r.json()})")
check(r.json()["current_resin"] == "Standard Clear V5", "...naming what it's recorded as holding now")
check(r.json()["vessel"]["reactor_name"] == "Tank A", "...naming the vessel that needs confirming")

r = client.post("/api/pouring/changeover",
                 json={"reactor_name": "Tank A", "new_resin": "Draft Grey V5", "station": STATION,
                       "shift": "Shift 1"}, headers=CSRF)
check(r.status_code == 200, f"confirming the changeover succeeds (got {r.status_code})")
r = lookup(STATION, "Draft Grey V5")
check(r.json()["status"] == "matched", "after confirming, the same lookup now reads as matched")

r = client.post("/api/pouring/changeover",
                 json={"reactor_name": "No Such Tank", "new_resin": "X", "station": STATION,
                       "shift": "Shift 1"}, headers=CSRF)
check(r.status_code == 400, f"changing over a vessel that doesn't exist is refused (got {r.status_code})")

# --- ambiguous: two vessels on this pump both on this resin -----------------
crud.add_reactor(reactor_name="Tank B", max_capacity_l=200, asset_tag="TK-B", assigned_pump=STATION,
                 current_resin="Draft Grey V5")
r = lookup(STATION, "Draft Grey V5")
check(r.json()["status"] == "ambiguous", f"two matching vessels -> ambiguous (got {r.json()})")
check(set(r.json()["vessel_names"]) == {"Tank A", "Tank B"}, "...naming both, so a lead can fix it")

# --- no_vessel also covers 2+ UNLINKED vessels on the pump (see docstring) --
crud.link_vessel_to_pump("Tank A", "")   # unlink both from the station...
crud.link_vessel_to_pump("Tank B", "")
r = lookup(STATION, "Draft Grey V5")
check(r.json()["status"] == "no_vessel",
      f"zero vessels physically on the pump -> no_vessel, same status as 2+ (got {r.json()})")
check({o["value"] for o in r.json()["options"]} == {"Tank A", "Tank B"},
      "...and both are offered as link targets")
check(any("(TK-A)" in o["label"] for o in r.json()["options"]),
      "...labelled with their asset tag, via shared._vessel_label")

r = client.post("/api/pouring/link-vessel", json={"reactor_name": "Tank A", "station": STATION},
                 headers=CSRF)
check(r.status_code == 200, f"linking a vessel to the pump succeeds (got {r.status_code})")
r = lookup(STATION, "Draft Grey V5")
check(r.json()["status"] == "matched", "once linked and on-resin, the lookup reads as matched again")

r = client.post("/api/pouring/link-vessel", json={"reactor_name": "No Such Tank", "station": STATION},
                 headers=CSRF)
check(r.status_code == 400, f"linking a vessel that doesn't exist is refused (got {r.status_code})")

# --- mark-empty: gated behind the mark_reactor_empty ability ----------------
# The earlier changeover onto "Draft Grey V5" already opened a filling on
# Tank A by itself (see the note above) - nothing to open by hand here.
batch_id = crud.current_batch("Tank A").get("id")
check(bool(batch_id), "the changeover above already left an open filling on Tank A")
r = lookup(STATION, "Draft Grey V5")
check(r.json()["batch"]["id"] == batch_id, "the open filling shows up in the lookup's batch field")

r = client.post("/api/pouring/mark-empty", json={"reactor_name": "Tank A"}, headers=CSRF)
check(r.status_code == 200, f"an operator (granted mark_reactor_empty by role) can mark it empty (got {r.status_code})")
r = lookup(STATION, "Draft Grey V5")
check(r.json()["batch"] is None, "after marking empty, the lookup shows no open filling")

r = client.post("/api/pouring/mark-empty", json={"reactor_name": "Tank A"}, headers=CSRF)
check(r.status_code == 400, f"marking an already-empty vessel empty again is refused (got {r.status_code})")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = lookup(STATION, "Draft Grey V5")
check(r.status_code == 401, f"reactor-lookup refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API POURING CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API POURING ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
