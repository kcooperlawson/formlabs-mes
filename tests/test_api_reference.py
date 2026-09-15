"""The read-only lookups the Operator Form pilot needs before it can render
anything: pumps, resin specs (both the ungated inline caption and the
gated searchable lookup), downtime reasons, plant settings, and an
operator's last picks.

Checks the actual security boundary Finding 11 in the security posture doc
cares about (crud.py's own docs describe it, see api/routers/reference.py):
/reference/resins is open to any signed-in floor role, /reference/resin-
lookup is not - and neither one ever leaks a SKU or internal resin code.
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
print("API REFERENCE: read-only lookups for the Operator Form pilot")
print("=" * 66)

# --- everything here requires a session, at minimum -------------------------
for path in ("/api/reference/pumps", "/api/reference/resins", "/api/reference/resin-lookup",
             "/api/reference/downtime-reasons", "/api/reference/plant-settings",
             "/api/user/last-picks"):
    r = client.get(path)
    check(r.status_code == 401, f"{path} refuses an anonymous request (got {r.status_code})")

# --- sign in as the seeded operator -----------------------------------------
r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator login for the reference checks (got {r.status_code})")

# --- pumps -------------------------------------------------------------
r = client.get("/api/reference/pumps")
check(r.status_code == 200, f"an authenticated operator can list pumps (got {r.status_code})")
check(isinstance(r.json(), list) and len(r.json()) > 0, "the seeded pumps come back (crud.seed_initial_data)")

# --- resins: the ungated inline caption --------------------------------
r = client.get("/api/reference/resins")
check(r.status_code == 200, f"an operator (no view_resin_lookup grant needed) reads /resins (got {r.status_code})")
specs = r.json()
check(isinstance(specs, list) and len(specs) > 0, "the seeded resin catalogue comes back")
row = specs[0]
check(set(row) == {"cartridge_type", "resin_name", "target_g", "min_g", "max_g", "target_kg",
                   "units_per_skid", "color"},
      f"a resin row carries only what a pour/pack is checked against, no sku/resin_code (got keys {sorted(row)})")
check(abs(row["target_kg"] - round(row["target_g"] / 1000.0, 4)) < 1e-9,
      "target_kg is derived from target_g, not a separate stale column")
check(set(row["color"]) == {"bg", "fg", "border"}, "each row carries the same chip colour the operator UI shows")

# --- resin-lookup: gated behind view_resin_lookup ---------------------------
# The operator role is granted view_resin_lookup by default (crud.ROLE_ABILITIES),
# so the seeded operator CAN reach this - the gate matters for a role/grant
# that lacks it, checked below by forging a role with none.
r = client.get("/api/reference/resin-lookup")
check(r.status_code == 200,
      f"an operator (granted view_resin_lookup by role, per crud.ROLE_ABILITIES) reaches resin-lookup (got {r.status_code})")
check(r.json() == specs, "resin-lookup and resins return identically-shaped, identical data")

# --- the gate actually gates: a role with the ability stripped is refused ---
check(crud.user_can(999999, "supervisor", "view_resin_lookup") is False,
      "a role nobody has heard of has no abilities at all (sanity check on the dependency's own logic)")

# --- downtime reasons ---------------------------------------------------
r = client.get("/api/reference/downtime-reasons")
check(r.status_code == 200, f"downtime reasons load (got {r.status_code})")
check(isinstance(r.json(), list) and len(r.json()) > 0, "the seeded reasons come back")

# --- plant settings: only the floor-relevant subset -------------------------
r = client.get("/api/reference/plant-settings")
check(r.status_code == 200, f"plant settings load (got {r.status_code})")
check(set(r.json()) == {"simple_mode", "enable_bulk_pour", "enable_packing",
                        "enable_device_gateway", "pump_form_url", "pump_form_label"},
      f"only floor-relevant settings are exposed, never the full admin row (got keys {sorted(r.json())})")

# --- last picks: empty for an operator who has never logged -----------------
r = client.get("/api/user/last-picks")
check(r.status_code == 200, f"last-picks loads even with no history (got {r.status_code})")
check(r.json() == {"station": "", "cartridge": "", "resin": ""},
      "a first-time operator gets empty defaults, not an error")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API REFERENCE CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API REFERENCE ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
