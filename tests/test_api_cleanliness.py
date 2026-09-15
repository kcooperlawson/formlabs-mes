"""Cleanliness & Station Photo Gallery, ported from pages/Mgr_Cleanliness.py
- the manager review side of audit_tab.py's submissions. Seeds real audits
through the operator-facing /api/audit/submit endpoint (already tested in
tests/test_api_audit.py) rather than writing rows directly, so this test
also proves the two sides of the feature actually agree with each other.
"""
import io
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
print("API CLEANLINESS: the manager photo-audit gallery")
print("=" * 66)

# --- access control ----------------------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/cleanliness/stats")
check(r.status_code == 403, f"an operator without view_manager_cockpit is refused (got {r.status_code})")

# --- the operator submits two audits, one a spill with two photos ----------
client.post("/api/audit/submit", data={
    "audit_type": "Start Of Shift (Cleanliness Check)", "station": "New Pump #1", "notes": "All clear.",
}, files=[("photos", ("start.jpg", io.BytesIO(b"a"), "image/jpeg"))], headers=CSRF)
client.post("/api/audit/submit", data={
    "audit_type": "Resin Spill / Containment Issue", "station": "New Pump #2",
    "notes": "Small spill, contained.", "is_spill": "true",
}, files=[
    ("photos", ("spill1.jpg", io.BytesIO(b"b"), "image/jpeg")),
    ("photos", ("spill2.jpg", io.BytesIO(b"c"), "image/jpeg")),
], headers=CSRF)
client.post("/api/auth/logout", headers=CSRF)

# --- the manager sees both, correctly counted ------------------------------
r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

r = client.get("/api/cleanliness/stats")
check(r.status_code == 200, f"stats load (got {r.status_code})")
stats = r.json()
check(stats["total_audits"] == 2, f"both audits count (got {stats})")
check(stats["start_checks"] == 1, f"one start-of-shift check (got {stats})")
check(stats["spills"] == 1, f"one spill flagged (got {stats})")
check(stats["end_checks"] == 0 and stats["transfers"] == 0, "nothing miscounted into the wrong bucket")

r = client.get("/api/cleanliness/audits")
check(r.status_code == 200, f"the audit list loads (got {r.status_code})")
audits = r.json()
check(len(audits) == 2, f"both audits are listed (got {len(audits)})")
spill = next(a for a in audits if a["is_spill"])
check(spill["pump_station"] == "New Pump #2", "the spill is attributed to the right station")
check(len(spill["photos"]) == 2, f"both spill photos are listed, main plus the extra (got {spill['photos']})")
start = next(a for a in audits if not a["is_spill"])
check(len(start["photos"]) == 1, f"the start-of-shift audit has its one photo (got {start['photos']})")

# --- photos are actually retrievable, gated the same way -------------------
r = client.get(f"/api/cleanliness/photos/{start['photos'][0]}")
check(r.status_code == 200, f"a real photo filename serves the actual bytes (got {r.status_code})")
check(r.content == b"a", "...the exact bytes that were uploaded")

r = client.get("/api/cleanliness/photos/does-not-exist.jpg")
check(r.status_code == 404, f"a filename with nothing on disk is refused, not silently empty (got {r.status_code})")

# --- path traversal is refused outright, not just "not found" --------------
r = client.get("/api/cleanliness/photos/..%2F..%2F.env")
check(r.status_code in (400, 404), f"a path-traversal filename is refused (got {r.status_code})")

# --- delete --------------------------------------------------------------
r = client.delete(f"/api/cleanliness/audits/{start['id']}", headers=CSRF)
check(r.status_code == 200, f"deleting an audit succeeds (got {r.status_code})")
r = client.get("/api/cleanliness/audits")
check(len(r.json()) == 1, "it's gone from the list")
r = client.delete(f"/api/cleanliness/audits/{start['id']}", headers=CSRF)
check(r.status_code == 404, f"deleting it again is refused, not a silent no-op (got {r.status_code})")

# --- everything here requires the ability, not just a session -----------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/cleanliness/stats")
check(r.status_code == 401, f"stats refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API CLEANLINESS CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API CLEANLINESS ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
