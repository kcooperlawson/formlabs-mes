"""External Reporting & Google Cloud Sync, ported from
pages/Mgr_Google_Sync.py: linking a destination sheet, previewing/exporting
the payload, and pushing to a linked sheet. Gated by export_data.

Doesn't assume a fresh boot() means zero destinations: migration
0013_sheet_targets carries the old single .env webhook forward as a shared
"Plant sheet" row if GOOGLE_SHEETS_WEBHOOK is set wherever this runs, which
it is on this machine - so every check below filters to the "Weekly
Report" row this test itself adds, rather than asserting the list is
empty.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

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
AGG = "📊 Aggregated Calculated Metrics (KPI Summary)"
RAW = "📋 Raw Production Audit Stream"
ALL_TIME = "🌐 All Time History"


def find(rows, name):
    return next((r for r in rows if r["name"] == name), None)


print("=" * 66)
print("API GOOGLE SYNC: External Reporting & Google Cloud Sync")
print("=" * 66)

# --- gated behind export_data ------------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/google-sync/targets")
check(r.status_code == 403, f"an operator without export_data is refused (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/google-sync/targets")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

r = client.get("/api/google-sync/targets")
check(r.status_code == 200 and find(r.json(), "Weekly Report") is None,
      f"the destination this test is about to add isn't there yet (got {r.status_code})")

# --- URL classification, the whole point of sheet_sync.classify_url --------
r = client.get("/api/google-sync/classify-url", params={"url": "https://docs.google.com/spreadsheets/d/abc123/edit"})
check(r.json()["kind"] == "sheet" and not r.json()["ok"], f"a spreadsheet link is recognized and refused (got {r.json()})")

r = client.get("/api/google-sync/classify-url", params={"url": "https://script.google.com/macros/s/AKfyc.../exec"})
check(r.json()["kind"] == "webhook" and r.json()["ok"], f"a real web-app address is accepted (got {r.json()})")

# --- linking a destination ---------------------------------------------
r = client.post("/api/google-sync/targets", json={
    "name": "", "url": "https://docs.google.com/spreadsheets/d/abc123/edit",
}, headers=CSRF)
check(r.status_code == 400, f"a spreadsheet link is refused at add-time too (got {r.status_code})")

r = client.post("/api/google-sync/targets", json={
    "name": "Weekly Report", "url": "https://script.google.com/macros/s/AKfyc123/exec", "is_shared": False,
}, headers=CSRF)
check(r.status_code == 201, f"a well-formed link saves (got {r.status_code}, {r.text[:150]})")
target = r.json()
check(target["label"] == "Weekly Report — Plant Lead", f"the label names the owner (got {target['label']})")
check(target["editable"] is True, "the owner can edit their own sheet")
check(target["owner_user_id"] is not None, "a newly-added destination always has a real owner")
target_id = target["id"]

r = client.post("/api/google-sync/targets", json={
    "name": "Weekly Report", "url": "https://script.google.com/macros/s/AKfycDIFFERENT/exec",
}, headers=CSRF)
check(r.status_code == 400, f"the same person adding the same name twice is refused (got {r.status_code})")

# --- a second, non-admin manager account --------------------------------
crud.create_user("shift_lead", "lead@x.local", "leadpin1", "Shift Lead", "manager", shift="Shift 1")
client.post("/api/auth/logout", headers=CSRF)
r = client.post("/api/auth/login", json={"username": "shift_lead", "pin": "leadpin1"}, headers=CSRF)
check(r.status_code == 200, f"the second manager account can log in (got {r.status_code})")

r = client.get("/api/google-sync/targets")
check(find(r.json(), "Weekly Report") is None, "a private sheet stays invisible to a different, non-admin manager")

r = client.put(f"/api/google-sync/targets/{target_id}", json={"name": "Hijacked"}, headers=CSRF)
check(r.status_code == 404, f"a manager can't even find someone else's private sheet to edit it (got {r.status_code})")

client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
r = client.put(f"/api/google-sync/targets/{target_id}", json={"is_shared": True}, headers=CSRF)
check(r.status_code == 200 and r.json()["is_shared"] is True, f"the owner marks their sheet shared (got {r.status_code})")

client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "shift_lead", "pin": "leadpin1"}, headers=CSRF)
r = client.get("/api/google-sync/targets")
shared_view = find(r.json(), "Weekly Report")
check(shared_view is not None, f"once shared, the second manager can see it (got {r.json()})")
check(shared_view["editable"] is False, "...but still can't edit it - it belongs to whoever added it")

r = client.put(f"/api/google-sync/targets/{target_id}", json={"name": "Hijacked"}, headers=CSRF)
check(r.status_code == 403, f"editing a shared-but-not-owned sheet is refused (got {r.status_code})")
r = client.delete(f"/api/google-sync/targets/{target_id}", headers=CSRF)
check(r.status_code == 403, f"deleting it is refused too (got {r.status_code})")

client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)

# --- the connection test against an address that can't be reached ----------
r = client.post(f"/api/google-sync/targets/{target_id}/test", headers=CSRF)
check(r.status_code == 200 and r.json()["ok"] is False, f"testing an unpublished/fake script reports unreachable, not a crash (got {r.json()})")

# --- export preview: empty, then with real data -----------------------------
r = client.get("/api/google-sync/export-preview", params={"export_mode": AGG, "horizon": ALL_TIME})
check(r.status_code == 200 and r.json()["row_count"] == 0, f"nothing logged yet reads as empty (got {r.json()})")

r = client.get("/api/google-sync/export-preview", params={"export_mode": "bogus", "horizon": ALL_TIME})
check(r.status_code == 400, f"an unrecognized export mode is refused (got {r.status_code})")

crud.add_hourly_log("Demo Operator", "New Pump #1", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=100, scrap_empty=5, scrap_filled=0, log_type="Hourly Bottle Count")
crud.add_hourly_log("Demo Operator", "Pack-Out Station", "Shift 1", "V2", "Standard Clear V5", "L1",
                    bottles=80, scrap_empty=0, scrap_filled=0, log_type="Packing Count")

r = client.get("/api/google-sync/export-preview", params={"export_mode": AGG, "horizon": ALL_TIME})
body = r.json()
check(body["row_count"] == 2,
      f"the aggregate groups by station too, so pouring (New Pump #1) and packing (Pack-Out Station) land in separate rows (got {body})")
pour_row = next(r for r in body["rows"] if r["Pump Station"] == "New Pump #1")
pack_row = next(r for r in body["rows"] if r["Pump Station"] == "Pack-Out Station")
check(pour_row["Units Poured"] == 100 and pour_row["Units Packed"] == 0,
      f"the pouring row's own units land under Units Poured, not Units Packed (got {pour_row})")
check(pack_row["Units Packed"] == 80 and pack_row["Units Poured"] == 0,
      f"...and the packing row's units land the other way round (got {pack_row})")
check(pour_row["Scrap Reject Units"] == 5 and pour_row["Quality FPY (%)"] == round(100 / 105 * 100, 2),
      f"scrap and FPY are computed from the real totals (got {pour_row})")
check("Volume Output (Liters)" in body["columns"], "the aggregated columns include the renamed metric names")

r = client.get("/api/google-sync/export-preview", params={"export_mode": RAW, "horizon": ALL_TIME})
raw_body = r.json()
check(raw_body["row_count"] == 2, f"the raw stream keeps every log as its own row (got {raw_body['row_count']})")
check("log_type" in raw_body["columns"], "the raw stream keeps the underlying column names, not the renamed KPI ones")

# --- xlsx export ------------------------------------------------------
r = client.get("/api/google-sync/export.xlsx", params={"export_mode": AGG, "horizon": ALL_TIME, "columns": "Date,Units Poured"})
check(r.status_code == 200, f"the Excel download succeeds (got {r.status_code})")
check(r.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      f"...with the right content type (got {r.headers.get('content-type')})")
check(len(r.content) > 0, "...and an actual non-empty file body")

# --- pushing to a sheet ---------------------------------------------------
r = client.post("/api/google-sync/push", json={
    "target_id": target_id, "export_mode": AGG, "horizon": ALL_TIME, "columns": [],
}, headers=CSRF)
check(r.status_code == 400, f"pushing with no columns selected is refused (got {r.status_code})")

r = client.post("/api/google-sync/push", json={
    "target_id": target_id, "export_mode": AGG, "horizon": ALL_TIME, "columns": ["Date", "Units Poured"],
}, headers=CSRF)
check(r.status_code == 200 and r.json()["ok"] is False,
      f"pushing to an unreachable webhook fails gracefully, not with a 500 (got {r.status_code}, {r.text[:150]})")

targets_after = crud.get_sheet_targets_df()
pushed_row = targets_after[targets_after["id"] == target_id].iloc[0]
check(pushed_row["last_status"] is not None and pushed_row["last_rows"] == 0,
      f"the failed push is still recorded against the destination (got last_status={pushed_row['last_status']!r})")

# --- deleting a destination ----------------------------------------------
r = client.delete(f"/api/google-sync/targets/{target_id}", headers=CSRF)
check(r.status_code == 200, f"the owner can delete their own sheet (got {r.status_code})")
r = client.get("/api/google-sync/targets")
check(find(r.json(), "Weekly Report") is None, "it's gone from the list")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = client.get("/api/google-sync/targets")
check(r.status_code == 401, f"google-sync refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API GOOGLE SYNC CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API GOOGLE SYNC ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
