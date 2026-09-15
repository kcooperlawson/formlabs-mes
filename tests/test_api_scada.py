"""Live SCADA - the manager/admin dashboard, ported from Home.py's
post-login body. Uses horizon="specific" with today's actual date for the
aggregation checks rather than horizon="live", since "live" depends on
whether a shift happens to be running at whatever real time this test
executes - "specific" filters by date only and is deterministic regardless
of the clock.
"""
import pathlib
import sys
from datetime import date

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
TODAY = str(date.today())

print("=" * 66)
print("API SCADA: the manager/admin plant dashboard")
print("=" * 66)

# --- gated behind view_scada, not a bare role check -------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/scada/overview")
check(r.status_code == 403, f"an operator without view_scada is refused (got {r.status_code})")

_session = crud.ScopedSession()
operator_id = _session.query(crud.User).filter_by(username="operator").first().id
_session.close()
crud.grant_ability(operator_id, "view_scada", by_name="Test Setup", by_role="admin")
r = client.get("/api/scada/overview")
check(r.status_code == 200, f"...but once granted the ability, the same operator can reach it (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/scada/overview")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- bad params are rejected, not silently ignored --------------------------
r = client.get("/api/scada/overview", params={"horizon": "nonsense"})
check(r.status_code == 400, f"an unrecognized horizon is refused (got {r.status_code})")
r = client.get("/api/scada/overview", params={"sort": "nonsense"})
check(r.status_code == 400, f"an unrecognized sort is refused (got {r.status_code})")

# --- an empty plant reads as empty, not broken ------------------------------
r = client.get("/api/scada/overview", params={"horizon": "specific", "date": TODAY})
check(r.status_code == 200, f"overview loads with nothing logged (got {r.status_code})")
body = r.json()
check(body["health"]["state"] == "no-record", f"health says nothing has ever been logged (got {body['health']})")
check(body["pouring"]["liters_output"] == 0, "zero liters, not an error, with nothing logged")
check(body["filters"] == {"pumps": [], "resins": [], "operators": [], "shifts": [], "dates": []},
      "filter dropdowns start empty too")

# --- seed a known day of production and check the math ---------------------
crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=100, scrap_empty=5, scrap_filled=0, log_type="Hourly Bottle Count")
crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V1", "Standard Black V5", "L2",
                    bottles=50, scrap_empty=0, scrap_filled=0, log_type="Hourly Bottle Count")
crud.add_hourly_log("Demo Packer", "Pack-Out Station", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=80, scrap_empty=0, scrap_filled=0, log_type="Packing Count")

r = client.get("/api/scada/overview", params={"horizon": "specific", "date": TODAY})
check(r.status_code == 200, f"overview loads with real data (got {r.status_code})")
body = r.json()
check(body["health"]["state"] != "no-record", "health no longer reads as never-logged")

pouring = body["pouring"]
check(pouring["total_scrap"] == 5, f"scrap sums across both pours (got {pouring['total_scrap']})")
check(abs(pouring["yield_pct"] - (150 / 155 * 100)) < 0.01, f"yield is units/(units+scrap) (got {pouring['yield_pct']})")
check({c["cartridge_type"] for c in pouring["cart_type_counts"]} == {"V2", "V1"},
      f"cart_type_counts covers every format actually poured, not a fixed pair (got {pouring['cart_type_counts']})")
v2_count = next(c["units"] for c in pouring["cart_type_counts"] if c["cartridge_type"] == "V2")
check(v2_count == 100, f"V2 count is exactly the V2 pour, not blended with V1 (got {v2_count})")
check(pouring["liters_output"] > 0, "liters_output is computed, not zero, once something is poured")

check({e["operator"] for e in pouring["leaderboard"]} == {"Demo Operator"},
      f"the leaderboard names the operator who actually poured (got {pouring['leaderboard']})")

packing = body["packing"]
check(packing["total_packed"] == 80, f"packing total reflects the Packing Count log only (got {packing['total_packed']})")
check(packing["unpacked_wip"] == 150 - 80, f"unpacked WIP is poured minus packed (got {packing['unpacked_wip']})")
check(len(packing["by_resin_lot"]) == 1 and packing["by_resin_lot"][0]["units"] == 80,
      f"packed-by-resin-lot breaks down correctly (got {packing['by_resin_lot']})")

check(set(body["filters"]["pumps"]) == {"New Pump #1", "Pack-Out Station"},
      f"the pump filter now offers what was actually logged against (got {body['filters']['pumps']})")
check(set(body["filters"]["resins"]) == {"Standard Clear V5", "Standard Black V5"},
      f"...and likewise for resins (got {body['filters']['resins']})")

# --- filtering by pump actually narrows the numbers -------------------------
r = client.get("/api/scada/overview", params={"horizon": "specific", "date": TODAY, "pump": "Pack-Out Station"})
check(r.json()["pouring"]["liters_output"] == 0,
      "filtering to the pack-out station excludes every pouring log (nothing was poured there)")
check(r.json()["packing"]["total_packed"] == 80, "...but its own packing total is unaffected")

# --- horizon="live" is structurally sound regardless of the real clock -----
r = client.get("/api/scada/overview", params={"horizon": "live"})
check(r.status_code == 200, f"horizon=live loads regardless of whether a shift happens to be running (got {r.status_code})")
check(r.json()["pouring"]["trajectory"] is not None, "the trajectory card is present in live mode")
r = client.get("/api/scada/overview", params={"horizon": "week"})
check(r.json()["pouring"]["trajectory"] is None, "...and absent outside live mode, same as the original")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API SCADA CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API SCADA ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
