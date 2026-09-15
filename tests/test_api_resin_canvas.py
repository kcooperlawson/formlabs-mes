"""Formlabs Master Resin Specification Lookup Table, ported from
pages/Mgr_Resin_Canvas.py: the manager-only SKU/resin-code table, plus
add/edit/delete. Gated by manage_resins on every route, including the read.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from _boot import boot  # noqa: E402  (throwaway database, refuses production)

boot(fresh=True)

from starlette.testclient import TestClient  # noqa: E402

import api.main  # noqa: E402
from resin_palette import resin_color  # noqa: E402

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
print("API RESIN CANVAS: Master Resin Specification table")
print("=" * 66)

# --- gated behind manage_resins for the READ too, not just writes ----------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in (got {r.status_code})")
r = client.get("/api/resin-canvas")
check(r.status_code == 403, f"an operator without manage_resins is refused even the read (got {r.status_code})")
client.post("/api/auth/logout", headers=CSRF)

r = client.get("/api/resin-canvas")
check(r.status_code == 401, f"the endpoint refuses an anonymous request too (got {r.status_code})")

r = client.post("/api/auth/login", json={"username": "manager", "pin": "admin123"}, headers=CSRF)
check(r.status_code == 200, f"the seeded admin/manager account can log in (got {r.status_code})")

# --- the seeded master catalog is already there -----------------------------
r = client.get("/api/resin-canvas")
check(r.status_code == 200, f"the table loads (got {r.status_code})")
seeded = r.json()
check(len(seeded) > 0, "the seeded master catalog isn't empty")
check(all("sku" in row and "resin_code" in row for row in seeded),
      "unlike the public resin list, this one carries sku and resin_code")

# --- adding a resin ----------------------------------------------------
r = client.post("/api/resin-canvas", json={
    "cartridge_type": "V2", "sku": "RS-F2-CUST-01", "resin_code": "FLCUST01",
    "resin_name": "", "actual_spec_g": 1110, "min_weight_g": 1100, "max_weight_g": 1125,
}, headers=CSRF)
check(r.status_code == 400, f"a blank formulation name is refused (got {r.status_code})")

r = client.post("/api/resin-canvas", json={
    "cartridge_type": "V2", "sku": "RS-F2-CUST-01", "resin_code": "FLCUST01",
    "resin_name": "High-Temp Clear V3", "actual_spec_g": 1110, "min_weight_g": 1100, "max_weight_g": 1125,
}, headers=CSRF)
check(r.status_code == 201, f"a well-formed new resin saves (got {r.status_code}, {r.text[:150]})")
new_spec = r.json()
check(new_spec["resin_name"] == "High-Temp Clear V3" and new_spec["target_kg"] == 1.11,
      f"the response carries the row back, including the derived kg (got {new_spec})")
check(new_spec["color"] == resin_color("High-Temp Clear V3"),
      f"with no colour override, the colour resolves from the name's family (got {new_spec['color']})")

r = client.post("/api/resin-canvas", json={
    "cartridge_type": "Pigment", "sku": "RS-PIG-01", "resin_code": "FLPIG01",
    "resin_name": "Cyan Pigment", "actual_spec_g": 500, "min_weight_g": 490, "max_weight_g": 510,
    "color_tag": "#123456",
}, headers=CSRF)
check(r.status_code == 201, f"an explicit colour override is accepted (got {r.status_code})")
check(r.json()["color"] == "#123456", f"...and used verbatim instead of the family default (got {r.json()['color']})")

# --- format filter and search ------------------------------------------
r = client.get("/api/resin-canvas", params={"format": "Pigment"})
pigments = r.json()
check(all(row["cartridge_type"] == "Pigment" for row in pigments), "the format filter narrows to that format only")
check(any(row["resin_name"] == "Cyan Pigment" for row in pigments), "...and the new pigment shows up in it")

r = client.get("/api/resin-canvas", params={"search": "high-temp"})
found = r.json()
check(len(found) == 1 and found[0]["resin_name"] == "High-Temp Clear V3",
      f"search matches on resin name, case-insensitively (got {found})")

r = client.get("/api/resin-canvas", params={"search": "FLPIG01"})
found = r.json()
check(len(found) == 1 and found[0]["resin_name"] == "Cyan Pigment",
      f"search also matches on resin code (got {found})")

# --- editing a spec ------------------------------------------------------
spec_id = new_spec["id"]
r = client.put(f"/api/resin-canvas/{spec_id}", json={
    "actual_spec_g": 1120, "min_weight_g": 1110, "max_weight_g": 1130, "color_tag": "#ABCDEF",
}, headers=CSRF)
check(r.status_code == 200, f"a well-formed edit saves (got {r.status_code}, {r.text[:150]})")
updated = r.json()
check(updated["actual_spec_g"] == 1120 and updated["min_weight_g"] == 1110 and updated["max_weight_g"] == 1130,
      f"the edited tolerances stick (got {updated})")
check(updated["color"] == "#ABCDEF", "...and the colour picked in the edit form sticks too")
check(updated["sku"] == "RS-F2-CUST-01" and updated["resin_code"] == "FLCUST01",
      "editing tolerances never touches sku/resin_code - the edit form doesn't show them")

r = client.put("/api/resin-canvas/999999", json={
    "actual_spec_g": 1, "min_weight_g": 1, "max_weight_g": 1, "color_tag": "#000000",
}, headers=CSRF)
check(r.status_code == 404, f"editing a nonexistent spec is refused (got {r.status_code})")

# --- deleting a spec ------------------------------------------------------
r = client.delete(f"/api/resin-canvas/{spec_id}", headers=CSRF)
check(r.status_code == 200, f"deleting an existing spec succeeds (got {r.status_code})")
r = client.get("/api/resin-canvas", params={"search": "High-Temp Clear V3"})
check(r.json() == [], "the deleted resin no longer appears")

r = client.delete(f"/api/resin-canvas/{spec_id}", headers=CSRF)
check(r.status_code == 404, f"deleting it again is refused, not silently ok (got {r.status_code})")

# --- everything here requires the ability, including writes -----------------
client.post("/api/auth/logout", headers=CSRF)
client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
r = client.post("/api/resin-canvas", json={
    "cartridge_type": "V2", "sku": "x", "resin_code": "x", "resin_name": "x",
    "actual_spec_g": 1, "min_weight_g": 1, "max_weight_g": 1,
}, headers=CSRF)
check(r.status_code == 403, f"an operator cannot add a resin either (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API RESIN CANVAS CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API RESIN CANVAS ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
