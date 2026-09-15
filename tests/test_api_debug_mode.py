"""Manager/admin "Impersonate Operator for Testing" (Debug Mode), ported
from Operator_Form.py's own superuser debug block: a manager or admin can
log a pour, packing count, downtime, audit or note "as" a real operator for
testing or on that operator's behalf, without their own name landing on the
record. See api/deps.py's resolve_operator_name - the one function every
write in pouring/packing/downtime/audit/notes/summary/reference now asks,
mirroring how every one of those originally read pouring_tab.py's shared
`current_user` instead of the session's own name.

The property under test throughout: an `as_operator` override only ever
takes effect for a manager or admin session. An operator or packer sending
the same field gets it silently ignored, exactly like the "Impersonate
Operator" selectbox never rendering for them in the original.
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
RESIN = "Standard Clear V5"


def login(username, pin):
    return client.post("/api/auth/login", json={"username": username, "pin": pin}, headers=CSRF)


print("=" * 66)
print("API DEBUG MODE: managers/admins logging or reviewing as an operator")
print("=" * 66)

# --- active-operators: manager/admin only, mirrors the selectbox itself ----
r = login("manager", "admin123")
check(r.status_code == 200, f"manager can log in (got {r.status_code})")

r = client.get("/api/reference/active-operators")
check(r.status_code == 200, f"manager can list active operators (got {r.status_code})")
names = r.json()
check("Sasha" in names and "Demo Operator" in names,
      f"both seeded operators are offered (got {names})")
check("No Operators Found" not in names, "the crud-level empty-list placeholder never leaks into the API")

client.post("/api/auth/logout", headers=CSRF)
r = login("operator", "1234")
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/reference/active-operators")
check(r.status_code == 403, f"an operator can't reach the impersonation picker's own data (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

CART = "V2"  # a GATED_FORMATS member; every format needs an entered_lot

# --- an operator's own as_operator is ignored -------------------------------
login("operator", "1234")
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN, "entered_lot": "2411A0001",
    "bottles_filled": "10", "as_operator": "Sasha",
}, headers=CSRF)
check(r.status_code == 200, f"operator's own pour still submits (got {r.status_code}, {r.text[:200]})")
mine = crud.get_production_logs_df(operator="Demo Operator")
check(not mine.empty and mine.iloc[-1]["operator_name"] == "Demo Operator",
      "a real operator can't attribute their own log to someone else via as_operator")
sasha_logs = crud.get_production_logs_df(operator="Sasha")
check(sasha_logs.empty, "...and nothing landed on the impersonated name either")
client.post("/api/auth/logout", headers=CSRF)

# --- a manager's as_operator DOES take effect -------------------------------
login("manager", "admin123")
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN, "entered_lot": "2411A0002",
    "bottles_filled": "25", "as_operator": "Sasha",
}, headers=CSRF)
check(r.status_code == 200, f"manager can submit a pour in Debug Mode (got {r.status_code}, {r.text[:200]})")
sasha_logs = crud.get_production_logs_df(operator="Sasha")
check(not sasha_logs.empty and sasha_logs.iloc[-1]["bottles_filled"] == 25,
      f"the pour is attributed to the impersonated operator, not 'Plant Lead' (got {sasha_logs.to_dict('records')})")
plant_lead_logs = crud.get_production_logs_df(operator="Plant Lead")
check(plant_lead_logs.empty, "the manager's own name never appears on a Debug Mode log")

# --- a manager with no as_operator falls back to their own name ------------
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN, "entered_lot": "2411A0003",
    "bottles_filled": "5",
}, headers=CSRF)
check(r.status_code == 200, f"manager can still log a pour as themselves (got {r.status_code}, {r.text[:200]})")
plant_lead_logs = crud.get_production_logs_df(operator="Plant Lead")
check(not plant_lead_logs.empty and plant_lead_logs.iloc[-1]["bottles_filled"] == 5,
      "omitting as_operator falls back to the caller's own name")

# --- packing submit honors the same override --------------------------------
r = client.post("/api/packing/submit", json={
    "cartridge_type": "V2", "resin": RESIN, "lot_number": "L-1",
    "units_packed": 3, "as_operator": "Sasha",
}, headers=CSRF)
check(r.status_code == 200, f"manager can log packing in Debug Mode (got {r.status_code})")
sasha_packing = crud.get_production_logs_df(operator="Sasha")
sasha_packing = sasha_packing[sasha_packing["log_type"] == "Packing Count"]
check(not sasha_packing.empty, "the packing count is also attributed to the impersonated operator")

# --- notes: sent, and read back, as the impersonated operator --------------
r = client.post("/api/notes", json={"message": "Testing debug mode", "as_operator": "Sasha"}, headers=CSRF)
check(r.status_code == 200, f"manager can send a note in Debug Mode (got {r.status_code})")
r = client.get("/api/notes", params={"as_operator": "Sasha"})
check(r.status_code == 200 and any(n["message"] == "Testing debug mode" for n in r.json()),
      "the note shows up under the impersonated operator's own note history")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} DEBUG MODE CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} DEBUG MODE ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
