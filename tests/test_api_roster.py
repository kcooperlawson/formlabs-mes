"""Floor Personnel Administration, ported from pages/Mgr_Roster.py. Checks
the fix made during this port: pin_policy_error is now enforced on both
provisioning and PIN reset, where neither crud.create_user/update_user_pin
nor the original page enforced it at all.
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
print("API ROSTER: Floor Personnel Administration")
print("=" * 66)

# --- access control ----------------------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/roster")
check(r.status_code == 403, f"an operator without manage_people is refused (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- the seeded floor accounts show up, managers/admins don't --------------
r = client.get("/api/roster")
check(r.status_code == 200, f"roster loads (got {r.status_code})")
usernames = {u["username"] for u in r.json()}
check(usernames == {"operator", "sasha"}, f"only floor roles are listed, not the admin account (got {usernames})")

# --- provisioning is refused for anything but operator/packer ---------------
r = client.post("/api/roster/provision", json={
    "full_name": "Sneaky Manager", "email": "sneaky@x.local", "username": "sneaky",
    "pin": "123456", "role": "manager", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 400, f"this page can't provision a manager account (got {r.status_code})")

# --- pin_policy_error is enforced on provisioning - THE fix ---------------
r = client.post("/api/roster/provision", json={
    "full_name": "New Guy", "email": "newguy@x.local", "username": "newguy",
    "pin": "1", "role": "operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 400, f"a one-character PIN is refused on provisioning (got {r.status_code}, {r.text[:150]})")

r = client.post("/api/roster/provision", json={
    "full_name": "New Guy", "email": "newguy@x.local", "username": "newguy",
    "pin": "1234", "role": "operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 201, f"a policy-compliant PIN provisions fine (got {r.status_code})")

r = client.get("/api/roster")
check(any(u["username"] == "newguy" for u in r.json()), "the new operator shows up in the roster")

r = client.post("/api/roster/provision", json={
    "full_name": "Dupe", "email": "newguy@x.local", "username": "someone-else",
    "pin": "1234", "role": "operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 400, f"a duplicate email is refused (got {r.status_code})")

# --- pin_policy_error is enforced on reset too - THE other half of the fix -
new_guy_id = next(u["id"] for u in client.get("/api/roster").json() if u["username"] == "newguy")
r = client.post("/api/roster/reset-pin", json={"user_id": new_guy_id, "new_pin": "12"}, headers=CSRF)
check(r.status_code == 400, f"a too-short reset PIN is refused (got {r.status_code}, {r.text[:150]})")

r = client.post("/api/roster/reset-pin", json={"user_id": new_guy_id, "new_pin": "9999"}, headers=CSRF)
check(r.status_code == 200, f"a policy-compliant reset succeeds (got {r.status_code})")

# --- the new PIN actually works to log in -----------------------------
r = client.post("/api/auth/login", json={"username": "newguy", "pin": "9999"}, headers=CSRF)
check(r.status_code == 200, f"the reset PIN actually authenticates (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

# --- resetting a non-floor or nonexistent account is refused ----------------
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
r = client.post("/api/roster/reset-pin", json={"user_id": 999999, "new_pin": "1234"}, headers=CSRF)
check(r.status_code == 404, f"resetting a nonexistent account is refused (got {r.status_code})")

# --- everything here requires the ability -------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/roster")
check(r.status_code == 401, f"roster refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API ROSTER CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API ROSTER ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
