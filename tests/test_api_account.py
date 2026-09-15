"""The account panel, ported from ui_shell.py's shared "Account & Preferences"
popover: self-service credential changes, avatar upload, and feedback
submission. Every signed-in role reaches this, not just managers.
"""
import io
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import crud  # noqa: E402
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
print("API ACCOUNT: the shared Account & Preferences panel")
print("=" * 66)

r = client.get("/api/account/feedback")
check(r.status_code == 401, f"an anonymous request is refused (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"the seeded operator can log in (got {r.status_code})")

# --- credentials -----------------------------------------------------------
r = client.put("/api/account/credentials", json={"full_name": "Demo O. Updated", "username": "operator", "pin": ""}, headers=CSRF)
check(r.status_code == 200, f"updating just the display name succeeds (got {r.status_code})")
check(r.json()["full_name"] == "Demo O. Updated", f"the new name comes back immediately (got {r.json()})")
check(client.get("/api/auth/me").json()["full_name"] == "Demo O. Updated", "...and /auth/me reflects it too")

r = client.put("/api/account/credentials", json={"full_name": "Demo O. Updated", "username": "sasha", "pin": ""}, headers=CSRF)
check(r.status_code == 400, f"renaming yourself to an existing username is refused (got {r.status_code})")

r = client.put("/api/account/credentials", json={"full_name": "Demo O. Updated", "username": "operator", "pin": "12"}, headers=CSRF)
check(r.status_code == 400, f"a PIN under the operator minimum (4) is refused (got {r.status_code})")

r = client.put("/api/account/credentials", json={"full_name": "Demo O. Updated", "username": "operator", "pin": "4444"}, headers=CSRF)
check(r.status_code == 200, f"a PIN change at the minimum length succeeds (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)
r = client.post("/api/auth/login", json={"username": "operator", "pin": "4444"}, headers=CSRF)
check(r.status_code == 200, "...and the new PIN actually works to log in")

r = client.put("/api/account/credentials", json={"full_name": "  ", "username": "operator", "pin": ""}, headers=CSRF)
check(r.status_code == 200 and r.json()["full_name"] == "Demo O. Updated",
      f"a blank name leaves the existing one alone rather than blanking it (got {r.json() if r.status_code == 200 else r.status_code})")

# --- theme -------------------------------------------------------------
r = client.put("/api/account/theme", json={"theme": "Vaporwave 1984"}, headers=CSRF)
check(r.status_code == 200 and r.json()["preferred_theme"] == "Vaporwave 1984",
      f"a theme choice is saved and comes back on the user (got {r.status_code}, {r.json() if r.status_code == 200 else ''})")

r = client.get("/api/auth/me")
check(r.json()["preferred_theme"] == "Vaporwave 1984", "...and survives a fresh session lookup, not just the response of the write itself")

r = client.put("/api/account/theme", json={"theme": "  "}, headers=CSRF)
check(r.status_code == 400, f"a blank theme is refused rather than silently saved (got {r.status_code})")

r = client.put("/api/account/theme", json={"theme": "Formlabs Forge"}, headers=CSRF)
check(r.status_code == 200 and r.json()["preferred_theme"] == "Formlabs Forge", "switching back to the default is just another theme choice")

# An admin PIN policy is stricter (6) - login as the seeded admin to check it
# applies to THEIR OWN change too, not just ones an admin makes for others.
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
r = client.put("/api/account/credentials", json={"full_name": "Plant Lead", "username": "manager", "pin": "1234"}, headers=CSRF)
check(r.status_code == 400, f"an admin's own PIN change is held to the admin minimum too (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "4444"}, headers=CSRF)

# --- avatar ------------------------------------------------------------
tiny_png = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108020000009077"
    "53de0000000c4944415408d763f8ffff3f0005fe02fea739669d0000000049454e44ae426082")
r = client.post("/api/account/avatar", files={"file": ("me.png", io.BytesIO(tiny_png), "image/png")}, headers=CSRF)
check(r.status_code == 200, f"uploading a PNG avatar succeeds (got {r.status_code})")
avatar_filename = r.json()["avatar_filename"]
check(bool(avatar_filename), f"the response carries the new filename (got {r.json()})")

r = client.get(f"/api/account/avatar/{avatar_filename}")
check(r.status_code == 200 and r.content == tiny_png, f"the uploaded avatar is servable and byte-identical (got {r.status_code})")

r = client.post("/api/account/avatar", files={"file": ("virus.exe", io.BytesIO(b"not an image"), "application/octet-stream")}, headers=CSRF)
check(r.status_code == 400, f"a non-image extension is refused (got {r.status_code})")

r = client.post("/api/account/avatar", files={"file": ("huge.png", io.BytesIO(b"x" * (5 * 1024 * 1024 + 1)), "image/png")}, headers=CSRF)
check(r.status_code == 400, f"an oversized file is refused rather than silently saved (got {r.status_code})")

r = client.get("/api/account/avatar/..%2F..%2F.env")
check(r.status_code in (400, 404), f"a path-traversal filename is refused outright (got {r.status_code})")
r = client.get("/api/account/avatar/does-not-exist.png")
check(r.status_code == 404, f"a filename with nothing on disk 404s, not a silent empty response (got {r.status_code})")

# --- feedback ----------------------------------------------------------
check(client.get("/api/account/feedback").json() == [], "no feedback submitted yet")

r = client.post("/api/account/feedback", json={"category": "App Bug / Error", "suggestion": "the pump picker is upside down"}, headers=CSRF)
check(r.status_code == 200, f"submitting feedback succeeds (got {r.status_code})")

r = client.post("/api/account/feedback", json={"category": "Not A Real Category", "suggestion": "x"}, headers=CSRF)
check(r.status_code == 400, f"an unrecognized category is refused (got {r.status_code})")

r = client.post("/api/account/feedback", json={"category": "General Feedback", "suggestion": "   "}, headers=CSRF)
check(r.status_code == 400, f"blank feedback text is refused, not silently swallowed (got {r.status_code})")

mine = client.get("/api/account/feedback").json()
check(len(mine) == 1 and mine[0]["status"] == "Open" and mine[0]["category"] == "App Bug / Error",
      f"my one submission shows up, Open, with the right category (got {mine})")

# The IT-side inbox (already covered by test_api_admin.py) sees the same row.
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
inbox = client.get("/api/admin/suggestions").json()
check(any(s["suggestion"] == "the pump picker is upside down" for s in inbox),
      f"the submission reaches IT's suggestions inbox too, not a separate store (got {inbox})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API ACCOUNT CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API ACCOUNT ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
