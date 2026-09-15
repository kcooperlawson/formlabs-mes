"""Notes from the Floor - the manager side of the Notes tab, ported from
pages/Mgr_Floor_Comms.py. Completes the loop tests/test_api_notes.py
started: an operator writes a note (api/routers/notes.py), a manager reads
and replies to it here, and the operator's own thread should show that
reply.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

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
print("API FLOOR COMMS: the manager side of Notes")
print("=" * 66)

# --- gated behind view_manager_cockpit --------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/floor-comms/operators")
check(r.status_code == 403, f"an operator without view_manager_cockpit is refused (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

# --- an operator writes a note ----------------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
client.post("/api/notes", json={"message": "Pump 2 is leaking a little at the valve."}, headers=CSRF)
client.post("/api/auth/logout", headers=CSRF)

# --- the manager sees them listed, and can tell who has written ------------
r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

r = client.get("/api/floor-comms/operators")
check(r.status_code == 200, f"the operator list loads (got {r.status_code})")
ops = {o["name"]: o["has_written"] for o in r.json()}
check(ops.get("Demo Operator") is True, f"Demo Operator shows as having written (got {ops})")
check("Sasha" in ops or "sasha" in [n.lower() for n in ops], "the other seeded operator is listed even though they haven't written")
check(ops.get(next(n for n in ops if n.lower() == "sasha"), None) is False,
      "...and correctly shows as NOT having written")

# --- reading the thread -------------------------------------------------
r = client.get("/api/floor-comms/thread", params={"operator_name": "Demo Operator"})
check(r.status_code == 200, f"the thread loads (got {r.status_code})")
thread = r.json()
check(len(thread) == 1, f"the operator's one note is there (got {len(thread)})")
check(thread[0]["message"] == "Pump 2 is leaking a little at the valve.", "...with the right text")
check(thread[0]["is_manager_reply"] is False, "...correctly attributed to the operator, not a manager reply")

r = client.get("/api/floor-comms/thread", params={"operator_name": "Sasha"})
check(r.json() == [], "an operator who hasn't written has an empty thread, not an error")

# --- replying ---------------------------------------------------------
r = client.post("/api/floor-comms/reply",
                 json={"operator_name": "Demo Operator", "message": "Thanks, sending someone now."},
                 headers=CSRF)
check(r.status_code == 200, f"the manager's reply sends (got {r.status_code})")

r = client.get("/api/floor-comms/thread", params={"operator_name": "Demo Operator"})
thread = r.json()
check(len(thread) == 2, f"the thread now has both messages (got {len(thread)})")
check(thread[1]["is_manager_reply"] is True, "the reply is marked as a manager reply")
check(thread[1]["sender_name"] == "Plant Lead",
      "attributed to 'Plant Lead' literally, matching the original's own (unfixed) behavior")

# --- and the operator sees the reply on their own side of the API ----------
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
r = client.get("/api/notes")
check(len(r.json()) == 2, f"the operator's own /notes now shows the manager's reply too (got {len(r.json())})")
check(r.json()[1]["is_manager_reply"] is True, "...correctly marked")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/floor-comms/operators")
check(r.status_code == 401, f"floor-comms refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API FLOOR COMMS CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API FLOOR COMMS ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
