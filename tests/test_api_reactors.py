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
check(r.json()[0]["batch"] is None, "the batch clears after marking empty")

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
