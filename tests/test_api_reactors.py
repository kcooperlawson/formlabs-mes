"""Live Reactor Fleet, ported from pages/Live_Reactors.py: the tank wall
(reusing reactor_vessel.vessel_svg directly), the fleet-management panel,
and the manager-initiated bulk pour. Also checks the one access-control
change made deliberately during this port: GET /fleet requires view_scada,
where the original page had no explicit ability gate on the view itself -
see api/routers/reactors.py's own docstring for why.
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

print("=" * 66)
print("API REACTORS: the Live Reactor Fleet page")
print("=" * 66)

# --- access control ----------------------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/reactors/fleet")
check(r.status_code == 403, f"an operator without view_scada is refused the fleet view (got {r.status_code})")
r = client.get("/api/reactors/manage-list")
check(r.status_code == 403, f"...and manage_reactors is a separate, still-refused door (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- an empty fleet ------------------------------------------------------
r = client.get("/api/reactors/fleet")
check(r.status_code == 200, f"fleet loads with nothing registered (got {r.status_code})")
check(r.json() == [], "no reactors yet")

# --- a reactor with NO optional fields set doesn't 500 ----------------------
# crud.add_reactor's own defaults (asset_tag="", bay_marker="", no pump, no
# resin) land as NULL in Postgres, which pandas reads back as float('nan') -
# not None or "" - and nan is truthy, so a naive `value or ""` lets it
# through unchanged. Regression coverage for that exact bug, caught live
# in a browser (a real reactor added via the manage panel with only a name
# and capacity, matching what "Add Permanent Reactor" actually submits).
r = client.post("/api/reactors", json={
    "reactor_name": "Bare Tank", "max_capacity_l": 500, "vessel_type": "ibc_tote",
    "asset_tag": "", "bay_marker": "",
}, headers=CSRF)
check(r.status_code == 201, f"a reactor with no tag/bay/pump/resin can be added (got {r.status_code})")
r = client.get("/api/reactors/fleet")
check(r.status_code == 200, f"the fleet endpoint doesn't 500 on a NULL-heavy row (got {r.status_code})")
bare = next(c for c in r.json() if c["reactor_name"] == "Bare Tank")
check(bare["asset_tag"] == "" and bare["bay_marker"] == "",
      f"nulls read back as empty strings, never the literal 'nan' (got {bare})")
check(bare["current_resin"] is None and bare["assigned_pump"] is None,
      f"...and current_resin/assigned_pump are null, not 'nan' or 'None' (got {bare})")
check(bare["is_idle"] is True, "a reactor with no resin assigned reads as idle, nan included")
check("<svg" in bare["svg"], "the SVG still renders even with every optional field unset")
r = client.get("/api/reactors/manage-list")
check(r.status_code == 200, f"manage-list also survives an all-NULL row (got {r.status_code})")
client.delete(f"/api/reactors/{next(c['id'] for c in r.json() if c['reactor_name'] == 'Bare Tank')}", headers=CSRF)

# --- add a reactor -------------------------------------------------------
r = client.post("/api/reactors", json={
    "reactor_name": "Tank A", "max_capacity_l": 200, "vessel_type": "ibc_tote",
    "asset_tag": "TK-A", "bay_marker": "F3",
}, headers=CSRF)
check(r.status_code == 201, f"adding a reactor succeeds (got {r.status_code})")

r = client.get("/api/reactors/manage-list")
check(r.status_code == 200 and len(r.json()) == 1, f"it shows up in the manage list (got {r.json()})")
reactor_id = r.json()[0]["id"]
check(r.json()[0]["vessel_type"] == "ibc_tote", "...with the vessel type set")

# --- an idle (empty) tank on the fleet view ---------------------------------
r = client.get("/api/reactors/fleet")
card = r.json()[0]
check(card["is_idle"] is True, f"a tank with no resin assigned reads as idle (got {card})")
check(card["current_resin"] is None, "...and current_resin is null, not the literal string 'None'")
check(card["fill_pct"] == 0.0, "...with 0% fill")
check("<svg" in card["svg"], "the vessel_svg output is embedded directly, not re-derived")
check(card["batch"] is None, "no filling has ever been opened on it")

# --- link it to a pump and resin, then it's live ----------------------------
r = client.put(f"/api/reactors/{reactor_id}", json={
    "vessel_type": "ibc_tote", "asset_tag": "TK-A", "bay_marker": "F3",
    "assigned_pump": "New Pump #1", "current_resin": "Standard Clear V5",
}, headers=CSRF)
check(r.status_code == 200, f"linking the pump and resin succeeds (got {r.status_code})")

r = client.get("/api/reactors/fleet")
card = r.json()[0]
check(card["is_idle"] is False, f"now it reads as live, not idle (got {card})")
check(card["current_resin"] == "Standard Clear V5", "...naming the resin")
check(card["remaining_l"] == 200, f"nothing has been drawn yet, so it reads full (got {card['remaining_l']})")
check(card["fill_pct"] == 100.0, "...100% fill")

# --- log a pour against it and watch the level move -------------------------
crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=50, scrap_empty=0, scrap_filled=0, log_type="Hourly Bottle Count")
r = client.get("/api/reactors/fleet")
card = r.json()[0]
check(card["remaining_l"] < 200, f"the tank level moves after a pour is logged against it (got {card['remaining_l']})")

# --- QC / batch status shows up once a filling is open ----------------------
crud.open_batch("Tank A", "Standard Clear V5", pump_station="New Pump #1")
r = client.get("/api/reactors/fleet")
card = r.json()[0]
check(card["batch"] is not None, "an open filling now shows up as a batch")
check(card["batch"]["qc_result"] == "", "...with no QC result yet")
check(card["can_mark_empty"] is True, "a manager (has manage_reactors) can mark it empty")

# --- mark empty, gated by manage_reactors (not mark_reactor_empty) ----------
r = client.post(f"/api/reactors/{reactor_id}/mark-empty", headers=CSRF)
check(r.status_code == 200 and r.json()["ok"] is True, f"marking it empty succeeds (got {r.json()})")
r = client.get("/api/reactors/fleet")
card = r.json()[0]
check(card["batch"] is None, "the batch clears after marking empty")
# The actual bug report: close_batch alone only stopped the QC/dwell-time
# clock on the ReactorBatch row - it left Reactor.current_resin exactly as
# it was, so the vessel still matched pours for that resin and still drew
# down on the tank wall as if it were full. mark_reactor_empty now clears
# it too, so the vessel reads idle the same way a never-filled one does.
check(card["is_idle"] is True, f"...and the vessel itself reads idle now, not still on its old resin (got {card})")
check(card["current_resin"] is None, "...current_resin actually clears, rather than staying stale")
check(card["fill_pct"] == 0.0, "...and the tank wall shows it empty, not still at its last poured level")

# --- mark filled: management's own counterpart, not inferred from a changeover
r = client.post(f"/api/reactors/{reactor_id}/mark-filled",
                 json={"resin_type": "Standard Clear V5", "lot_number": "L-9001", "filled_at": None, "note": "first fill"},
                 headers=CSRF)
check(r.status_code == 200 and r.json()["ok"] is True, f"marking a tank filled succeeds (got {r.status_code}, {r.text[:200]})")

r = client.get("/api/reactors/fleet")
card = r.json()[0]
check(card["is_idle"] is False and card["current_resin"] == "Standard Clear V5",
      f"the reactor itself now shows the resin, with no operator changeover involved (got {card})")
check(card["batch"] is not None, "...and a filling opened for it")

batches = crud.get_batches(reactor_name="Tank A")
check(batches[0]["resin_type"] == "Standard Clear V5" and batches[0]["lot_number"] == "L-9001",
      f"the new batch carries the lot number - dead on every changeover-opened batch until now (got {batches[0]})")
check(batches[0]["opened_by"] == "Plant Lead", f"attributed to the manager who marked it, not 'System' (got {batches[0]})")

# --- marking filled again closes the open batch first, rather than stacking -
first_batch_id = batches[0]["id"]
count_before = len(batches)
r = client.post(f"/api/reactors/{reactor_id}/mark-filled",
                 json={"resin_type": "Standard Clear V5", "lot_number": "L-9002", "filled_at": None, "note": ""},
                 headers=CSRF)
check(r.status_code == 200, f"topping off with the SAME resin succeeds (got {r.status_code}, {r.text[:200]}) - "
                            f"a resin changeover would never have fired for this, since nothing changed")
batches = crud.get_batches(reactor_name="Tank A")
check(len(batches) == count_before + 1,
      f"exactly one new filling opened, not one stacked on top of the still-open old one (got {count_before} -> {len(batches)})")
old = next(b for b in batches if b["id"] == first_batch_id)
check(old["open"] is False and old["emptied_at"] is not None, f"the first filling is now closed (got {old})")
check(batches[0]["lot_number"] == "L-9002", f"the new filling carries the new lot (got {batches[0]})")

# The actual bug report: reactor_draw_litres derives the tank wall's level
# from logged production, not from this ReactorBatch row - a top-off with
# the SAME resin (exactly this case) kept summing every pour logged since
# the FIRST fill straight through the second one, so the wall still read
# drawn-down immediately after a manager just said the tank was refilled.
r = client.get("/api/reactors/fleet")
card = r.json()[0]
check(card["fill_pct"] == 100.0,
      f"topping off resets the tank wall to full, not still drawn down from before (got {card['fill_pct']})")
check(card["remaining_l"] == 200.0, f"...remaining_l reads the full capacity (got {card['remaining_l']})")
check(card["lot"] == "L-9002", f"...and the new lot is what shows, not the one from before the top-off (got {card['lot']})")

# --- topping off with no lot on hand still has to reset the level -----------
# There's no real lot here to anchor a fresh batch to (see mark_reactor_filled's
# own docstring: a manager filling a tank isn't always looking at a printed
# lot), so this exercises the OTHER branch of the fix - a calibration
# adjustment that nets the running total back to zero drawn instead.
crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V2", "Standard Clear V5", "L-9002",
                    bottles=80, scrap_empty=0, scrap_filled=0, log_type="Hourly Bottle Count")
r = client.get("/api/reactors/fleet")
check(r.json()[0]["fill_pct"] < 100.0, "sanity check: the tank actually drew down after that pour")

r = client.post(f"/api/reactors/{reactor_id}/mark-filled",
                 json={"resin_type": "Standard Clear V5", "lot_number": "", "filled_at": None, "note": "no lot on hand"},
                 headers=CSRF)
check(r.status_code == 200, f"marking filled with no lot number still succeeds (got {r.status_code})")
r = client.get("/api/reactors/fleet")
check(r.json()[0]["fill_pct"] == 100.0,
      f"...and still resets the tank wall to full, even with nothing to anchor a fresh batch to (got {r.json()[0]['fill_pct']})")

# --- a back-dated fill time is honoured, for catching the record up after the fact
from datetime import datetime, timedelta  # noqa: E402
back_dated = (datetime.now() - timedelta(hours=5)).isoformat()
r = client.post(f"/api/reactors/{reactor_id}/mark-filled",
                 json={"resin_type": "Standard Black V5", "lot_number": "", "filled_at": back_dated, "note": ""},
                 headers=CSRF)
check(r.status_code == 200, f"a back-dated filled_at is accepted (got {r.status_code})")
r = client.get("/api/reactors/fleet")
check(r.json()[0]["batch"]["hours_in_reactor"] >= 4.9,
      f"...and the dwell clock reflects that back-dated time, not 'now' (got {r.json()[0]['batch']})")

r = client.post(f"/api/reactors/{reactor_id}/mark-filled",
                 json={"resin_type": "", "lot_number": "", "filled_at": None, "note": ""}, headers=CSRF)
check(r.status_code == 400, f"a blank resin is refused, not silently opened (got {r.status_code})")

r = client.post(f"/api/reactors/{reactor_id}/mark-filled",
                 json={"resin_type": "Standard Clear V5", "lot_number": "", "filled_at": "not-a-date", "note": ""},
                 headers=CSRF)
check(r.status_code == 422, f"an unparseable filled_at is refused, not silently treated as now (got {r.status_code})")

r = client.post("/api/reactors/999999/mark-filled",
                 json={"resin_type": "Standard Clear V5", "lot_number": "", "filled_at": None, "note": ""}, headers=CSRF)
check(r.status_code == 404, f"marking a reactor that doesn't exist filled 404s (got {r.status_code})")

client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
r = client.post(f"/api/reactors/{reactor_id}/mark-filled",
                 json={"resin_type": "Standard Clear V5", "lot_number": "", "filled_at": None, "note": ""}, headers=CSRF)
check(r.status_code == 403, f"an operator (no manage_reactors) cannot mark a tank filled (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)

# --- reassigning a vessel's resin through the raw fleet-management edit -----
# The actual bug report: this form used to just change the label on the
# Reactor row. Tank A is on Standard Black V5 here with a batch already 5
# hours old (from the back-dated mark-filled above) - reassigning it through
# this dropdown-and-Save, exactly the way a manager actually reaches it, has
# to behave like the changeover it is: close that batch, open a fresh one,
# reset the level, and leave a record of what happened and why.
old_batches = crud.get_batches(reactor_name="Tank A")
open_batch_id = next(b["id"] for b in old_batches if b["open"])
logs_before = len(crud.get_production_logs_df())

r = client.put(f"/api/reactors/{reactor_id}", json={
    "vessel_type": "ibc_tote", "asset_tag": "TK-A", "bay_marker": "F3",
    "assigned_pump": "New Pump #1", "current_resin": "Standard Clear V5",
}, headers=CSRF)
check(r.status_code == 200, f"reassigning the resin through the edit form succeeds (got {r.status_code})")

batches = crud.get_batches(reactor_name="Tank A")
old = next(b for b in batches if b["id"] == open_batch_id)
check(old["open"] is False, f"the old filling (Standard Black V5) is closed, not left running under a resin that's gone (got {old})")
new_open = next(b for b in batches if b["open"])
check(new_open["resin_type"] == "Standard Clear V5", f"a fresh filling opens for the new resin (got {new_open})")

r = client.get("/api/reactors/fleet")
card = r.json()[0]
check(card["current_resin"] == "Standard Clear V5", f"the fleet card shows the new resin (got {card['current_resin']})")
check(card["fill_pct"] == 100.0, f"...reset to full, not still drawn down as Standard Black V5 (got {card['fill_pct']})")

logs_after = crud.get_production_logs_df()
# Two rows, not one: the changeover note (like every other path that changes
# a vessel's resin writes) plus the calibration adjustment that's what
# actually resets the level - see reassign_reactor_resin/mark_reactor_filled.
check(len(logs_after) == logs_before + 2, f"the changeover and the level reset each leave their own row (got {len(logs_after) - logs_before})")
check(any("via fleet management" in n for n in logs_after.head(2)["notes"]),
      f"...and one of them says where the change came from (got {logs_after.head(2)['notes'].tolist()})")

# --- but an edit that leaves the resin alone is still just a plain edit -----
batches_before = len(crud.get_batches(reactor_name="Tank A"))
still_open_id = next(b["id"] for b in crud.get_batches(reactor_name="Tank A") if b["open"])
logs_before = len(crud.get_production_logs_df())
r = client.put(f"/api/reactors/{reactor_id}", json={
    "vessel_type": "ibc_tote", "asset_tag": "TK-A-2", "bay_marker": "F4",
    "assigned_pump": "New Pump #1", "current_resin": "Standard Clear V5",
}, headers=CSRF)
check(r.status_code == 200, f"an edit that doesn't touch the resin still succeeds (got {r.status_code})")
batches = crud.get_batches(reactor_name="Tank A")
check(len(batches) == batches_before, f"no new filling opened for a resin that didn't change (got {len(batches)}, was {batches_before})")
check(next(b for b in batches if b["id"] == still_open_id)["open"] is True,
      "...and the filling that was open stays open - nothing closed it either")
check(len(crud.get_production_logs_df()) == logs_before,
      "...nor write an audit log for nothing having changed")

# --- bulk pour from the reactor page, attributed to the MANAGER -------------
r = client.get("/api/reactors/manage-options")
check(r.status_code == 200, f"manage-options loads (got {r.status_code})")
check(set(v["value"] for v in r.json()["vessel_types"]) == {"bulk_vertical", "cone_mixer", "ibc_tote"},
      f"all three vessel kinds are offered (got {r.json()['vessel_types']})")

r = client.get("/api/reactors/bulk-candidates")
check(len(r.json()) == 1 and r.json()[0]["reactor_name"] == "Tank A",
      f"Tank A (has a resin) is a bulk-pour candidate (got {r.json()})")

r = client.get(f"/api/reactors/{reactor_id}/draw-info")
check(r.status_code == 200, f"draw-info loads (got {r.status_code})")
before_remaining = r.json()["remaining_l"]

logs_before = len(crud.get_production_logs_df(operator="Plant Lead"))
r = client.post(f"/api/reactors/{reactor_id}/bulk-pour",
                 json={"containers": 1, "amount_each": 20.0, "unit": "L", "note": "blue tote"},
                 headers=CSRF)
check(r.status_code == 200, f"a bulk pour from the reactor page succeeds (got {r.status_code}, {r.text[:200]})")
logs_after = len(crud.get_production_logs_df(operator="Plant Lead"))
check(logs_after == logs_before + 1, "attributed to the manager who logged it, not the operator")

r = client.get(f"/api/reactors/{reactor_id}/draw-info")
check(r.json()["remaining_l"] < before_remaining, "the tank level reflects the bulk pour too")

# --- an absurd bulk amount is refused, not silently capped ------------------
r = client.post(f"/api/reactors/{reactor_id}/bulk-pour",
                 json={"containers": 1, "amount_each": 9999.0, "unit": "L"}, headers=CSRF)
check(r.status_code == 400, f"an amount bigger than the vessel is refused (got {r.status_code})")

# --- reconciling a tank to what somebody actually read off it ---------------
# A real Streamlit-era feature (CHANGELOG 3.x's "Real tank reconciliation")
# that never got an endpoint or a screen in this rewrite - there was no way
# to correct a drifted level short of editing the database. The level is
# derived (see reactor_draw_litres), not stored, so this has to actually
# move the number, not just accept the request.
r = client.post(f"/api/reactors/{reactor_id}/reconcile",
                 json={"mode": "percent", "value": 40.0, "notes": "sight glass read"}, headers=CSRF)
check(r.status_code == 200 and r.json()["ok"] is True, f"a percentage reconciliation succeeds (got {r.json()})")
r = client.get("/api/reactors/fleet")
check(r.json()[0]["fill_pct"] == 40.0, f"the tank now reads exactly the percentage typed in (got {r.json()[0]['fill_pct']})")

r = client.post(f"/api/reactors/{reactor_id}/reconcile",
                 json={"mode": "liters", "value": 150.0, "notes": "exact gauge read"}, headers=CSRF)
check(r.status_code == 200 and r.json()["ok"] is True, f"an exact-litres reconciliation succeeds (got {r.json()})")
r = client.get("/api/reactors/fleet")
check(r.json()[0]["remaining_l"] == 150.0, f"...and lands exactly on the litres typed in (got {r.json()[0]['remaining_l']})")

r = client.post(f"/api/reactors/{reactor_id}/reconcile", json={"mode": "percent", "value": 140.0}, headers=CSRF)
check(r.status_code == 400, f"a percentage over 100 is refused (got {r.status_code})")

r = client.post("/api/reactors/999999/reconcile", json={"mode": "percent", "value": 50.0}, headers=CSRF)
check(r.status_code == 404, f"reconciling a reactor that doesn't exist 404s (got {r.status_code})")

client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
r = client.post(f"/api/reactors/{reactor_id}/reconcile", json={"mode": "percent", "value": 50.0}, headers=CSRF)
check(r.status_code == 403, f"an operator (no manage_reactors) cannot reconcile a tank (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)

# --- delete ---------------------------------------------------------
r = client.delete(f"/api/reactors/{reactor_id}", headers=CSRF)
check(r.status_code == 200, f"deleting the reactor succeeds (got {r.status_code})")
check(client.get("/api/reactors/manage-list").json() == [], "it's gone from the manage list")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/reactors/fleet")
check(r.status_code == 401, f"the fleet view refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API REACTORS CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API REACTORS ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
