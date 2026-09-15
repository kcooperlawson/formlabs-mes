"""Audit tab - cleanliness/changeover/spill photo audits, ported from
pages/operator_form/audit_tab.py. Unlike the checklist's cleanliness step,
this one never requires a photo (the original submits unconditionally),
so that's tested as an explicit contrast, not an oversight.
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
print("API AUDIT: cleanliness/changeover/spill photo audits")
print("=" * 66)

r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")

# --- a bad audit_type is refused ---------------------------------------
r = client.post("/api/audit/submit", data={
    "audit_type": "Not A Real Type", "station": "New Pump #1",
}, headers=CSRF)
check(r.status_code == 400, f"an unrecognized audit type is refused (got {r.status_code})")

# --- unlike checklist cleanliness, NO photo is required here ----------------
r = client.post("/api/audit/submit", data={
    "audit_type": "Station / Pump Transfer Check", "station": "New Pump #1",
    "notes": "Moving from Alpha Fast to White V5.",
}, headers=CSRF)
check(r.status_code == 200, f"an audit with no photo still submits (got {r.status_code}, {r.text[:200]})")

audits = crud.get_cleanliness_audits_df()
check(len(audits) == 1, "exactly one audit row exists now")
row = audits.iloc[0]
check(row["audit_type"] == "Station / Pump Transfer Check", "...with the audit type submitted")
check(row["is_spill"] == "No", "is_spill defaults to No when not sent")
check(row["image_filename"] is None or str(row["image_filename"]) == "nan",
      "no photo means no image_filename")

# --- a spill audit with photos ----------------------------------------------
r = client.post("/api/audit/submit", data={
    "audit_type": "Resin Spill / Containment Issue", "station": "New Pump #2",
    "notes": "Small spill, contained.", "is_spill": "true",
}, files=[
    ("photos", ("spill1.jpg", io.BytesIO(b"a"), "image/jpeg")),
    ("photos", ("spill2.jpg", io.BytesIO(b"b"), "image/jpeg")),
], headers=CSRF)
check(r.status_code == 200, f"a spill audit with two photos submits (got {r.status_code}, {r.text[:200]})")

audits = crud.get_cleanliness_audits_df()
spill_row = audits[audits["audit_type"] == "Resin Spill / Containment Issue"].iloc[0]
check(spill_row["is_spill"] == "Yes", "is_spill=true is recorded")
check(spill_row["image_filename"] is not None and str(spill_row["image_filename"]) != "nan",
      "the first photo is on the main audit row")

photos_by_audit = crud.get_cleanliness_audit_photos()
check(int(spill_row["id"]) in photos_by_audit, "the second photo hangs on the extras table")
check(len(photos_by_audit[int(spill_row["id"])]) == 1, "...exactly one extra, since two were sent")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.post("/api/audit/submit", data={"audit_type": "Station / Pump Transfer Check", "station": "x"},
                headers=CSRF)
check(r.status_code == 401, f"audit submit refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API AUDIT CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API AUDIT ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
