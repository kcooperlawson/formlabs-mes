"""Notes tab - a written note for the plant lead, ported from
pages/operator_form/notes_tab.py. Scoped to the signed-in operator's own
thread (crud.get_chat_history_df keys on operator_name), oldest first.
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
print("API NOTES: a written note for the plant lead")
print("=" * 66)

r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")

r = client.get("/api/notes")
check(r.status_code == 200, f"an empty thread loads fine (got {r.status_code})")
check(r.json() == [], "nothing noted yet")

r = client.post("/api/notes", json={"message": "Pump 2 is leaking a little at the valve."}, headers=CSRF)
check(r.status_code == 200, f"sending a note succeeds (got {r.status_code})")

r = client.post("/api/notes", json={"message": "Following up - it's worse this afternoon."}, headers=CSRF)
check(r.status_code == 200, f"a second note succeeds (got {r.status_code})")

r = client.get("/api/notes")
notes = r.json()
check(len(notes) == 2, f"both notes come back (got {len(notes)})")
check(notes[0]["message"] == "Pump 2 is leaking a little at the valve.",
      "oldest first, matching the chat-history ordering")
check(notes[0]["sender_name"] == "Demo Operator", "attributed to the sender")
check(notes[0]["is_manager_reply"] is False, "an operator's own note is never marked as a manager reply")
check(notes[0]["timestamp"].endswith("Z") or "+" in notes[0]["timestamp"],
      f"the timestamp is real ISO 8601, not pre-formatted into one timezone (got {notes[0]['timestamp']})")

# --- notes are scoped to the operator who wrote them ------------------------
r = client.post("/api/auth/login", json={"username": "sasha", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"a second operator can log in (got {r.status_code})")
r = client.get("/api/notes")
check(r.json() == [], "a different operator's thread starts empty, not shared with the first")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/notes")
check(r.status_code == 401, f"notes refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API NOTES CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API NOTES ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
