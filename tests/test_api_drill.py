"""Click any number, see what it is made of: /api/drill.

The checks that matter: a lot's total is its logs' total, a run's total is
the same figure the run's own progress counter shows (same matching rule,
not a second opinion), related rows come along, and an operator only ever
sees their own rows however they ask.
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
TODAY = date.today().isoformat()

print("=" * 66)
print("API DRILL: everything behind a number")
print("=" * 66)


def pour(op, pump, resin, lot, n, cart="V2"):
    crud.add_hourly_log(operator_name=op, pump_station=pump, shift="Shift 1", cartridge_type=cart,
                        resin_type=resin, lot_number=lot, bottles=n, scrap_empty=1, scrap_filled=0)


pour("Demo Operator", "Drill Pump A", "Grey", "LOT-D1", 100)
pour("Demo Operator", "Drill Pump A", "Grey", "lot-d1 ", 50)      # typed differently, same lot
pour("Someone Else", "Drill Pump B", "Grey", "LOT-D1", 30)
pour("Someone Else", "Drill Pump B", "Black", "LOT-D2", 70)
crud.create_assigned_run("Reactor 1", 5000, "Grey", "V2", 1000, "Demo Operator",
                         "Drill Pump A", "LOT-D1", "")   # returns units, not the id
from db_core import ScopedSession  # noqa: E402
from models import AssignedRun  # noqa: E402
_s = ScopedSession()
run_id = _s.query(AssignedRun.id).filter(AssignedRun.lot_number == "LOT-D1").scalar()
_s.close()
crud.open_batch("Drill Tank", "Grey", lot_number="LOT-D1", pump_station="Drill Pump A")

# --- as a manager: the whole floor ------------------------------------------
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)

r = client.get("/api/drill", params={"lot": "LOT-D1"})
check(r.status_code == 200, f"a lot can be drilled into (got {r.status_code} {r.text[:200]})")
body = r.json()
check(body["summary"]["units"] == 180 and body["summary"]["logs"] == 3,
      f"a lot's total is every log against it, however the lot was typed (got {body['summary']['units']}/{body['summary']['logs']})")
check({row["key"] for row in body["summary"]["breakdown"]["operator"]} == {"Demo Operator", "Someone Else"},
      "...broken down by who poured it")
check({row["key"] for row in body["summary"]["breakdown"]["pump"]} == {"Drill Pump A", "Drill Pump B"},
      "...and which pump")
check(body["summary"]["scrap_empty"] == 3, f"...with the scrap against it (got {body['summary']['scrap_empty']})")
check(any(x["id"] == run_id for x in body["runs"]), "the run for that lot comes along")
check(any(b["reactor_name"] == "Drill Tank" for b in body["batches"]), "...and the tank batch it came out of")
check(body["scope"] == "everyone", "a manager sees everyone")

r = client.get("/api/drill", params={"run_id": run_id})
body = r.json()
check(body["summary"]["units"] == 150,
      f"a run counts its own pump's logs of that resin and lot - not the other pump's (got {body['summary']['units']})")
check(body["run"]["current_units"] == body["summary"]["units"],
      f"...which is exactly the run's own progress figure (run says {body['run']['current_units']}, drill says {body['summary']['units']})")

r = client.get("/api/drill", params={"pump": "Drill Pump B", "date_from": TODAY, "date_to": TODAY})
body = r.json()
check(body["summary"]["units"] == 100, f"a pump's day is that pump's logs (got {body['summary']['units']})")
check({row["key"] for row in body["summary"]["breakdown"]["lot"]} == {"LOT-D1", "LOT-D2"},
      "...with the lots poured on it, each of which can be drilled into next")

r = client.get("/api/drill", params={"resin": "Grey", "operator": "Someone Else"})
check(r.json()["summary"]["units"] == 30, f"filters combine (got {r.json()['summary']['units']})")

check(client.get("/api/drill").status_code == 400, "asking about nothing is refused plainly")
check(client.get("/api/drill", params={"run_id": 999999}).status_code == 404, "an unknown run is a 404")
check(client.get("/api/drill", params={"date_from": "tuesday"}).status_code == 400, "a bad date is refused")
# "Drill Tank" has a batch but was never registered as a vessel - it still has
# a history worth showing, and must not be read as "every pour in the plant".
tank = client.get("/api/drill", params={"reactor": "Drill Tank"}).json()
check(len(tank["batches"]) == 1 and tank["summary"]["logs"] == 0,
      f"an unregistered vessel shows its batches and no one else's pours (got {len(tank['batches'])} batches, {tank['summary']['logs']} logs)")

# --- as an operator: their own rows, whatever they ask for -------------------
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
body = client.get("/api/drill", params={"lot": "LOT-D1"}).json()
check(body["scope"] == "self", "an operator is scoped to themselves")
check(body["summary"]["units"] == 150 and all(l["operator_name"] == "Demo Operator" for l in body["logs"]),
      f"...and sees only their own pours of a shared lot (got {body['summary']['units']})")
body = client.get("/api/drill", params={"lot": "LOT-D1", "operator": "Someone Else"}).json()
check(all(l["operator_name"] == "Demo Operator" for l in body["logs"]),
      "...even when they ask for somebody else by name")

client.post("/api/auth/logout", headers=CSRF)
check(client.get("/api/drill", params={"lot": "LOT-D1"}).status_code == 401, "anonymous is refused")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API DRILL CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API DRILL ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
