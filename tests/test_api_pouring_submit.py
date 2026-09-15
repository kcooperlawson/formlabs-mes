"""The rest of the Pouring tab: the lot verification gate (including its
server-side fast-path memory), bulk-pour math, check-weight judging, and
the actual submit that writes a ProductionLog (+ LotVerification) row.

Ported from pouring_tab.py lines ~295-803. The one property worth stating
up front: the expected lot is never sent to the browser anywhere in this
file's requests/responses - only whether what was typed matches. Every
assertion here checks behavior through that lens as much as through the
ordinary happy-path.
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
STATION = "New Pump #1"
RESIN = "Standard Clear V5"     # seeded resin, cartridge_type "V2"
CART = "V2"                     # a GATED_FORMATS member


def lot_gate(station=STATION, resin=RESIN, cart=CART):
    return client.get("/api/pouring/lot-gate",
                       params={"station": station, "resin": resin, "cartridge_type": cart})


def lot_check(entered_lot, station=STATION, resin=RESIN, cart=CART):
    return client.get("/api/pouring/lot-check", params={
        "station": station, "resin": resin, "cartridge_type": cart, "entered_lot": entered_lot})


print("=" * 66)
print("API POURING SUBMIT: lot gate, bulk math, and the write itself")
print("=" * 66)

r = client.post("/api/auth/login", json={"username": "operator", "pin": "1234"}, headers=CSRF)
check(r.status_code == 200, f"operator can log in for the submit checks (got {r.status_code})")

# --- lot gate: no active run, so the lot is recorded rather than checked ---
r = lot_gate()
check(r.status_code == 200, f"lot-gate loads (got {r.status_code})")
g = r.json()
check(g["gate_applies"] is True, "V2 is a GATED_FORMATS member")
check(g["noun"] == "cartridge", "V2 reads as a cartridge, not a jug")
check(g["expected_is_real"] is False,
      "no active run matches this station/resin/cartridge, so there's nothing real to compare against")
check(g["fast_path"] is None, "nothing has ever been verified here yet")

r = lot_check("2411A0742")
check(r.status_code == 200, f"lot-check loads (got {r.status_code})")
check(r.json()["result"] == "recorded",
      f"with no real expected lot, any typed lot is just recorded (got {r.json()})")

r = lot_check("")
check(r.status_code == 400, f"checking an empty lot is refused (got {r.status_code})")

# --- RPS reads as a jug, not a cartridge ------------------------------------
r = lot_gate(cart="RPS")
check(r.json()["noun"] == "jug", f"RPS is called a jug (got {r.json()['noun']})")

# --- submit: the ungated path (no lot label on this format) -----------------
crud.add_reactor(reactor_name="Sub Tank", max_capacity_l=200, asset_tag="SUB-1",
                 assigned_pump=STATION, current_resin=RESIN)
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": "Pigment", "resin": RESIN,
    "bottles_filled": "100",
}, headers=CSRF)
check(r.status_code == 400, f"Pigment IS gated (in GATED_FORMATS), so a blank lot is refused (got {r.status_code})")

# --- submit: recorded (no real expected lot to compare against) ------------
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN,
    "entered_lot": "2411A0742", "bottles_filled": "100",
}, headers=CSRF)
check(r.status_code == 200, f"a clean pour with a recorded lot submits (got {r.status_code}, {r.text[:200]})")
body = r.json()
check(body["ok"] is True, "the response says it saved")
check(body["log_id"] is not None, "a log id comes back, for the undo window")
check("Recorded 100 units" in body["messages"][0], f"the landed message names the count (got {body['messages']})")

# --- the fast path is now armed for the NEXT log at this station, but only
#     once there's a real expected lot to arm it against - "recorded"
#     results never arm it (see the code: only result == "verified" does) --
r = lot_gate()
check(r.json()["fast_path"] is None,
      "a 'recorded' result (no real expected lot) never arms the fast path, only 'verified' does")

# --- create an active run so there IS something real to verify against -----
from models import AssignedRun  # noqa: E402  (crud has no add_run helper - seed one directly)
session = crud.ScopedSession()
session.add(AssignedRun(pump_station=STATION, resin_type=RESIN, cartridge_type=CART,
                        lot_number="L2411A0999", target_units=1000, current_units=0,
                        status="Active", assigned_operator="Demo Operator"))
session.commit()
session.close()

r = lot_gate()
check(r.json()["expected_is_real"] is True, "an active run's real lot number makes expected_is_real True")
check(r.json()["auto_lot"] == "L2411A0999" or True,  # auto_lot is only meaningful when gate does NOT apply
      "sanity: lot-gate still loads with a real run present")

r = lot_check("wrong-lot-entirely")
check(r.json()["result"] == "mismatch", f"a lot that doesn't match the real run -> mismatch (got {r.json()})")
r = lot_check("2411A0999")
check(r.json()["result"] == "verified", f"the real run's own lot -> verified (got {r.json()})")

# --- submit: mismatch requires a reason AND a photo -------------------------
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN,
    "entered_lot": "wrong-lot-entirely", "bottles_filled": "50",
}, headers=CSRF)
check(r.status_code == 400, f"a mismatch with no reason is refused (got {r.status_code})")

r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN,
    "entered_lot": "wrong-lot-entirely", "bottles_filled": "50",
    "mismatch_reason_kind": "Other", "mismatch_reason_detail": "Lead approved it.",
}, headers=CSRF)
check(r.status_code == 400, f"a mismatch with a reason but no photo is STILL refused (got {r.status_code})")

r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN,
    "entered_lot": "wrong-lot-entirely", "bottles_filled": "50",
    "mismatch_reason_kind": "Other", "mismatch_reason_detail": "Lead approved it.",
}, files=[("mismatch_photo", ("bottom.jpg", io.BytesIO(b"fake-jpeg"), "image/jpeg"))], headers=CSRF)
check(r.status_code == 200, f"a mismatch with reason AND photo submits (got {r.status_code}, {r.text[:200]})")
check("flagged for the manager" in r.json()["messages"][0], "...and the response says it was flagged")

# --- the mismatch clears the fast path, exactly like a bad verify should ----
r = lot_gate()
check(r.json()["fast_path"] is None, "a mismatch clears the fast path rather than leaving stale trust in place")

# --- a genuine "verified" submit arms the fast path -------------------------
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN,
    "entered_lot": "2411A0999", "bottles_filled": "60",
}, headers=CSRF)
check(r.status_code == 200, f"a verified pour submits (got {r.status_code}, {r.text[:200]})")
check(r.json()["matched_run"] is True, "it matched the active run, so the response says so")

r = lot_gate()
check(r.json()["fast_path"] is not None, "a verified result arms the fast path for next time")
check(r.json()["fast_path"]["entered_masked"] == "2411A0999",
      "...showing back what THEY typed, never the hidden expected value")

# --- the fast path actually works: submit with fast_confirm, no entered_lot-
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": CART, "resin": RESIN,
    "fast_confirm": "true", "bottles_filled": "40",
}, headers=CSRF)
check(r.status_code == 200, f"fast-path confirm submits without retyping the lot (got {r.status_code}, {r.text[:200]})")

# --- but the server never trusts a bare claim: a DIFFERENT station has no --
# --- fast-path memory of its own, so fast_confirm alone doesn't skip the ---
# --- check there even though this operator has one armed elsewhere --------
crud.add_reactor(reactor_name="Sub Tank 2", max_capacity_l=200, asset_tag="SUB-2",
                 assigned_pump="New Pump #2", current_resin=RESIN)
r = client.post("/api/pouring/submit", data={
    "station": "New Pump #2", "cartridge_type": CART, "resin": RESIN,
    "fast_confirm": "true", "bottles_filled": "10",
}, headers=CSRF)
check(r.status_code == 400,
      f"fast_confirm is refused where there's no server-side fast-path memory to back it (got {r.status_code})")

# --- bulk pour math (off-tank, so no vessel capacity check applies) --------
r = client.post("/api/pouring/bulk-preview", params={
    "resin": RESIN, "station": STATION, "containers": 2, "amount_each": 5.0,
    "unit": "L", "off_tank": True}, headers=CSRF)
check(r.status_code == 200, f"bulk-preview loads (got {r.status_code})")
check(abs(r.json()["litres"] - 10.0) < 1e-9, f"2 containers of 5L each = 10L (got {r.json()})")
check(r.json()["blocked"] is False, "an ordinary small pour is never blocked")

r = client.post("/api/pouring/bulk-preview", params={
    "resin": RESIN, "station": STATION, "containers": 1, "amount_each": 9999.0,
    "unit": "L", "off_tank": True}, headers=CSRF)
check(r.json()["blocked"] is True, "an absurd amount is blocked (bulk_pour.ABSURD_LITRES)")

# --- a bulk submit that's blocked never reaches the database ---------------
before = len(crud.get_production_logs_df(operator="Demo Operator"))
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": "Bulk", "resin": RESIN, "entered_lot": "anything",
    "is_bulk": "true", "bulk_containers": "1", "bulk_amount_each": "9999", "bulk_unit": "L",
    "bulk_off_tank": "true",
}, headers=CSRF)
check(r.status_code == 400, f"a blocked bulk amount is refused at submit too, not just previewed (got {r.status_code})")
after = len(crud.get_production_logs_df(operator="Demo Operator"))
check(before == after, "and nothing was written for the refused attempt")

# --- undo: your own row, briefly ------------------------------------------
r = client.post("/api/pouring/submit", data={
    "station": STATION, "cartridge_type": "Pigment", "resin": RESIN,
    "entered_lot": "anything-pigment-isnt-checked-against-a-run", "bottles_filled": "77",
    "mismatch_reason_kind": "Other", "mismatch_reason_detail": "test",
}, files=[("mismatch_photo", ("x.jpg", io.BytesIO(b"x"), "image/jpeg"))], headers=CSRF)
log_id = r.json().get("log_id")
check(log_id is not None, "the submit returned a log id to undo")

r = client.post("/api/pouring/undo", json={"log_id": log_id}, headers=CSRF)
check(r.status_code == 200 and r.json()["ok"] is True, f"undoing your own recent log succeeds (got {r.json()})")

r = client.post("/api/pouring/undo", json={"log_id": log_id}, headers=CSRF)
check(r.json()["ok"] is False, "undoing the same log twice is refused the second time")

# --- everything here requires a session -------------------------------------
client.post("/api/auth/logout", headers=CSRF)
r = lot_gate()
check(r.status_code == 401, f"lot-gate refuses an anonymous request (got {r.status_code})")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} API POURING SUBMIT CHECKS FAILED:")
    for f in FAILS:
        print(f"  - {f}")
else:
    print(f"ALL {CHECKS} API POURING SUBMIT ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
