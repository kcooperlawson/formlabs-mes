"""Proves the FastAPI backend boots against this codebase's real database
layer, and that its whole auth surface - login, logout, session-restore,
the CSRF header check - behaves the way the migration plan says it must.

Everything api/ imports (crud, models, db_core) is exactly what the
Streamlit pages already run on; this is not a second database layer, just a
second front door onto the same one. Importing api.main runs crud.py's own
init_db()+seed_initial_data() the same way importing crud anywhere else
does, so the seeded "operator"/"1234" and "manager"/"admin123" accounts
(crud.seed_initial_data) exist without this file creating anything itself.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import api.main  # noqa: E402  (importing this runs init_db()+seed via crud.py)

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
print("API BOOT: the FastAPI app against the real crud.py/models.py layer")
print("=" * 66)

check(api.main.app is not None, "the FastAPI app object exists")

# --- unauthenticated ---------------------------------------------------
r = client.get("/api/auth/me")
check(r.status_code == 401, f"anonymous /me is refused (got {r.status_code})")

# --- CSRF header enforced on every state-changing route ---------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"})
check(r.status_code == 403, f"login without the CSRF header is refused (got {r.status_code})")

# --- bad credentials, without leaking which field was wrong -----------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "wrong"}, headers=CSRF)
check(r.status_code == 401, f"a wrong PIN is refused (got {r.status_code})")
check("Invalid" in r.json().get("detail", ""), "...and the message doesn't say which field was wrong")

# --- the seeded operator account can log in, remember=False ----------------
r = client.post("/api/auth/login",
                 json={"username": "operator", "pin": "1234", "remember": False}, headers=CSRF)
check(r.status_code == 200, f"the seeded operator can log in (got {r.status_code}, {r.text[:200]})")
body = r.json()
check(body.get("username") == "operator", "the login response is the operator's own record")
check(body.get("role") == "operator", "...with its real role")
set_cookie = r.headers.get("set-cookie", "")
check("mes_session=" in set_cookie, "a session cookie was set")
check("max-age" not in set_cookie.lower(), "remember=False gets a session-only cookie (no Max-Age)")

# --- the cookie carries identity across requests - /me is the whole restore -
r = client.get("/api/auth/me")
check(r.status_code == 200, "the session cookie alone restores identity")
check(r.json().get("username") == "operator", "...as the same account that logged in")

# --- logout revokes server-side, not just client-side -----------------------
r = client.post("/api/auth/logout", headers=CSRF)
check(r.status_code == 204, f"logout succeeds (got {r.status_code})")
r = client.get("/api/auth/me")
check(r.status_code == 401, "the same cookie no longer authenticates after logout")

# --- remember=True (the default) gets a persistent cookie -------------------
r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")
check(r.json().get("role") == "admin", "...as role 'admin', not 'manager' (crud.seed_initial_data seeds it that way)")
check("max-age" in r.headers.get("set-cookie", "").lower(),
      "remember defaults to True, so this cookie is persistent (has Max-Age)")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API BOOT CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API BOOT ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
