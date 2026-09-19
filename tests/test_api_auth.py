"""Self-registration and the plant-mode check, ported from Home.py's login
screen: the "REGISTER ACCESS" tab (a new operator can create their own
account, but never above Operator/Packer) and the pre-auth title picker.

Login/logout/me are already exercised implicitly by every other test file's
own login call; this file covers the two endpoints that are otherwise
untested.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import api.main  # noqa: E402

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
print("API AUTH: self-registration and the plant-mode check")
print("=" * 66)

# --- plant mode: readable before signing in ---------------------------
r = client.get("/api/auth/mode")
check(r.status_code == 200, f"the mode check needs no session (got {r.status_code})")
check(r.json() == {"simple_mode": True}, f"a fresh plant boots in logging mode (got {r.json()})")

# --- self-registration ------------------------------------------------
r = client.post("/api/auth/register", json={
    "full_name": "New Guy", "email": "newguy@plant.local", "username": "newguy",
    "pin": "4444", "role": "Operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 201, f"registering a new operator succeeds (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "newguy", "pin": "4444"}, headers=CSRF)
check(r.status_code == 200 and r.json()["role"] == "operator",
      f"the new account can sign in immediately, as an operator (got {r.status_code}, {r.json() if r.status_code == 200 else None})")
client.post("/api/auth/logout", headers=CSRF)

# The role picker only ever offers Operator/Packer, but the original page
# hard-coded role="operator" regardless of the selection - fixed in this
# port. Prove "Packer" actually creates a packer, not a silently-downgraded
# operator.
r = client.post("/api/auth/register", json={
    "full_name": "New Packer", "email": "newpacker@plant.local", "username": "newpacker",
    "pin": "4444", "role": "Packer", "shift": "Shift 2",
}, headers=CSRF)
check(r.status_code == 201, f"registering as Packer succeeds (got {r.status_code})")
r = client.post("/api/auth/login", json={"username": "newpacker", "pin": "4444"}, headers=CSRF)
check(r.status_code == 200 and r.json()["role"] == "packer",
      f"...and actually creates a packer account, not an operator (got {r.json() if r.status_code == 200 else r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

# Self-registration can never grant anything above Operator/Packer, even if
# a request is crafted by hand rather than sent through the picker.
r = client.post("/api/auth/register", json={
    "full_name": "Sneaky", "email": "sneaky@plant.local", "username": "sneaky",
    "pin": "444444", "role": "admin", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 400, f"a hand-crafted request asking for admin is refused (got {r.status_code})")

r = client.post("/api/auth/register", json={
    "full_name": "", "email": "x@x.com", "username": "x", "pin": "4444", "role": "operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 400, f"a blank name is refused (got {r.status_code})")

r = client.post("/api/auth/register", json={
    "full_name": "Bad Email", "email": "not-an-email", "username": "bademail",
    "pin": "4444", "role": "operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 400, f"a malformed email is refused (got {r.status_code})")

# The original never checked PIN strength on self-registration at all -
# fixed here to match the same policy every other PIN-setting path enforces.
r = client.post("/api/auth/register", json={
    "full_name": "Weak Pin", "email": "weakpin@plant.local", "username": "weakpin",
    "pin": "1", "role": "operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 400, f"a PIN under the operator minimum is refused, unlike the original (got {r.status_code})")

r = client.post("/api/auth/register", json={
    "full_name": "Dupe", "email": "newguy@plant.local", "username": "someoneelse",
    "pin": "4444", "role": "operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 409, f"a duplicate email is refused (got {r.status_code})")

r = client.post("/api/auth/register", json={
    "full_name": "Dupe2", "email": "someoneelse@plant.local", "username": "newguy",
    "pin": "4444", "role": "operator", "shift": "Shift 1",
}, headers=CSRF)
check(r.status_code == 409, f"a duplicate username is refused (got {r.status_code})")

# --- abilities: exposed on login/me, and a fresh grant shows up right away -
# The frontend has no other way to know what a specific person can reach -
# ManagerShell filters its own sidebar from exactly this list (see
# ManagerShell.tsx's canSeeManagerTab).
r = client.post("/api/auth/login", json={"username": "newguy", "pin": "4444"}, headers=CSRF)
newguy_id = r.json()["id"]
check(set(r.json()["abilities"]) == {"mark_reactor_empty", "view_resin_lookup"},
      f"a fresh operator's abilities are exactly their role's own defaults (got {r.json()['abilities']})")
client.post("/api/auth/logout", headers=CSRF)

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin can sign in to grant an ability (got {r.status_code})")
check("view_scada" in r.json()["abilities"], "an admin's own abilities already include everything, view_scada included")
r = client.post(f"/api/admin/users/{newguy_id}/abilities/view_scada", headers=CSRF)
check(r.status_code == 200, f"granting view_scada to the operator succeeds (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.post("/api/auth/login", json={"username": "newguy", "pin": "4444"}, headers=CSRF)
check("view_scada" in r.json()["abilities"],
      f"the grant shows up in the operator's own abilities on their very next login (got {r.json()['abilities']})")
r = client.get("/api/auth/me")
check("view_scada" in r.json()["abilities"], f"...and on /me too, not just the login response (got {r.json()['abilities']})")
client.post("/api/auth/logout", headers=CSRF)

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API AUTH CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API AUTH ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
