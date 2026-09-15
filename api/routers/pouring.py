"""Which tank a pour will be credited to, and the one genuinely tricky
mechanic in the whole Operator Form migration: tank changeover detection.

Ported from pages/operator_form/pouring_tab.py lines ~134-257. In Streamlit,
picking a new station or resin fires a full-page rerun that recomputes this
block before anything else on the page repaints - which is exactly the
flash-on-every-tap the rewrite exists to fix. Here it's a plain GET the
frontend calls from an onChange handler; only the small vessel-status panel
re-renders, nothing else on the page even notices.

Five branches, matching the five things the original inline block could
render (crud.reactor_for's own docstring: "Two matches is its own answer"):
  - "blank"       vessels_on_pump has exactly one vessel, holding nothing yet
  - "changeover"  ...holding a different resin - needs an operator confirm
  - "no_vessel"   zero or 2+ vessels physically on this pump (see note below)
  - "ambiguous"   reactor_for matched 2+ vessels on this pump AND this resin
  - "matched"     reactor_for found exactly one - the ordinary case

"no_vessel" also covers 2+ vessels already on the pump, matching the
original's own `if len(_on_pump) == 1: ... else:` - not a mistake carried
forward blindly, just deliberately unchanged: only-one-vessel is knowable
without asking, more-than-one only the operator standing there can sort
out, and either way there IS no derivable answer for reactor_for to find.
"""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

import bulk_pour
import crud
import fill_weight
from api import realtime
from api.shared import _vessel_label, bulk_vessel_state
from api.deps import get_current_user, require_ability, resolve_operator_name
from api.schemas.pouring import (
    BatchInfo, BulkPreviewOut, ChangeoverRequest, FastPathInfo, LinkVesselRequest,
    LotCheckOut, LotGateOut, MarkEmptyRequest, PourSubmitResponse, ReactorLookupOut,
    UndoRequest, UndoResponse, VesselChoice, VesselRef,
)
from api.uploads import to_streamlit_like

router = APIRouter(prefix="/pouring", tags=["pouring"])


def _vessel_ref(v: dict) -> VesselRef:
    tag = str(v.get("asset_tag") or "").strip() or v["reactor_name"]
    return VesselRef(reactor_name=v["reactor_name"], tag=tag, bay_marker=v.get("bay_marker"))


@router.get("/reactor-lookup", response_model=ReactorLookupOut)
def reactor_lookup(station: str, resin: str, user: dict = Depends(get_current_user)):
    vessel = crud.reactor_for(station, resin)

    if vessel is None:
        on_pump = crud.vessels_on_pump(station)
        if len(on_pump) == 1:
            v = on_pump[0]
            was = str(v.get("current_resin") or "").strip()
            if not was:
                return ReactorLookupOut(status="blank", vessel=_vessel_ref(v))
            return ReactorLookupOut(status="changeover", vessel=_vessel_ref(v), current_resin=was)

        options = crud.vessels_for_pump_picker(station)
        return ReactorLookupOut(
            status="no_vessel",
            options=[VesselChoice(value=v["reactor_name"], label=_vessel_label(v)) for v in options],
        )

    if vessel.get("ambiguous"):
        return ReactorLookupOut(status="ambiguous", vessel_names=vessel["ambiguous"])

    batch = crud.current_batch(vessel["reactor_name"])
    return ReactorLookupOut(
        status="matched",
        vessel=_vessel_ref(vessel),
        batch=BatchInfo(id=batch["id"], qc_result=batch["qc_result"], qc_open=batch["qc_open"],
                        hours_in_reactor=batch.get("hours_in_reactor")) if batch else None,
        can_mark_empty=crud.user_can(user["id"], user["role"], "mark_reactor_empty"),
    )


@router.post("/changeover")
def changeover(body: ChangeoverRequest, user: dict = Depends(get_current_user)):
    ok = crud.record_changeover(body.reactor_name, body.new_resin,
                                operator=resolve_operator_name(user, body.as_operator),
                                shift=body.shift, pump_station=body.station)
    if not ok:
        raise HTTPException(status_code=400, detail="That vessel could not be found.")
    return {"ok": True}


@router.post("/link-vessel")
def link_vessel(body: LinkVesselRequest, user: dict = Depends(get_current_user)):
    ok = crud.link_vessel_to_pump(body.reactor_name, body.station)
    if not ok:
        raise HTTPException(status_code=400, detail="That vessel could not be linked.")
    return {"ok": True}


@router.post("/mark-empty")
def mark_empty(body: MarkEmptyRequest, user: dict = Depends(require_ability("mark_reactor_empty"))):
    ok = crud.close_batch(body.reactor_name, by=resolve_operator_name(user, body.as_operator))
    if not ok:
        raise HTTPException(status_code=400, detail="No open filling on that vessel.")
    return {"ok": True}


# =============================================================================
# CARTRIDGE LOT VERIFICATION GATE
# -----------------------------------------------------------------------------
# Ported from pouring_tab.py lines ~295-505. The expected lot is never sent
# to the browser - only whether what was typed matches, exactly the same
# security property the masked Streamlit field had (there, the comparison
# ran server-side in the same Python process that rendered the page; here
# it runs server-side in this endpoint instead - the value still never
# reaches client-visible state either way).
#
# The "fast path" (skip retyping the lot when nothing physical has changed)
# needs real server-side memory to keep that property: a client-held
# "verified last time" flag would be a client asserting its own security
# check passed, which /submit must never trust. This is a plain in-process
# dict rather than a new database table - it's a UX cache, not a source of
# truth (the source of truth is the LotVerification row /submit writes),
# and this app is already one uvicorn process per plant PC, the same single-
# process model Streamlit's own st.session_state relied on. Keyed by
# (user_id, station) rather than by browser session, so it actually survives
# a page reload - an improvement over the Streamlit version, not a
# deliberately-preserved quirk: losing the fast path on every refresh was
# never a security feature, just an accident of where the state lived.
# =============================================================================
_LOT_GATE_MEMORY: dict[tuple[int, str], dict] = {}


def _lot_context(station: str, resin: str, cart_code: str) -> dict:
    gate_applies = cart_code in crud.GATED_FORMATS
    words = crud.container_words(cart_code)

    norm = lambda s: str(s).strip().lower()
    df_runs = crud.get_assigned_runs_df()
    match = df_runs[
        (df_runs["pump_station"].apply(norm) == norm(station))
        & (df_runs["resin_type"].apply(norm) == norm(resin))
        & (df_runs["cartridge_type"].apply(norm) == norm(cart_code))
        & (df_runs["status"].isin(["Active", "Pouring"]))
    ]
    matched_run = not match.empty
    placeholder = f"LOT-{datetime.now():%Y%m%d}-01"
    # .get()'s default only fires when the column itself is absent, never for
    # a present-but-empty value - matching pouring_tab.py's own
    # `row.get("lot_number", placeholder)` exactly, including its one wart:
    # an active run somehow saved with a NULL lot_number reads as auto_lot
    # "None", same as it always has.
    auto_lot = str(match.iloc[0].get("lot_number", placeholder)) if matched_run else placeholder
    return {
        "gate_applies": gate_applies,
        "words": words,
        "expected_lot": auto_lot,
        "expected_is_real": not crud.is_placeholder_lot(auto_lot),
        "auto_lot": auto_lot,
        "matched_run": matched_run,
    }


def _fast_path(user_id: int, station: str, expected_lot: str, resin: str,
               cart_code: str, expected_is_real: bool) -> dict | None:
    mem = _LOT_GATE_MEMORY.get((user_id, station))
    if not (mem and expected_is_real and mem.get("entered")):
        return None
    same_material = (mem["expected"] == expected_lot and mem["resin"] == resin
                     and mem["cart"] == cart_code)
    fresh = (datetime.now() - mem["ts"]) <= timedelta(hours=4)
    spot_check_due = mem.get("since_full", 0) >= 9
    return mem if (same_material and fresh and not spot_check_due) else None


def _judge_lot(expected_lot: str, expected_is_real: bool, typed: str) -> str:
    if not expected_is_real:
        return "recorded"
    return "verified" if crud.lots_match(expected_lot, typed) else "mismatch"


@router.get("/lot-gate", response_model=LotGateOut)
def lot_gate(station: str, resin: str, cartridge_type: str, user: dict = Depends(get_current_user)):
    ctx = _lot_context(station, resin, cartridge_type)
    fast = _fast_path(user["id"], station, ctx["expected_lot"], resin, cartridge_type,
                      ctx["expected_is_real"])
    return LotGateOut(
        gate_applies=ctx["gate_applies"],
        noun=ctx["words"]["noun"],
        field_label=ctx["words"]["field"],
        where_hint=ctx["words"]["where"],
        still_reads_label=ctx["words"]["still_reads"],
        expected_is_real=ctx["expected_is_real"],
        auto_lot=ctx["auto_lot"],
        matched_run=ctx["matched_run"],
        fast_path=FastPathInfo(since=fast["ts"].isoformat(), by=fast["by"], entered_masked=fast["entered"])
        if fast else None,
    )


@router.get("/lot-check", response_model=LotCheckOut)
def lot_check(station: str, resin: str, cartridge_type: str, entered_lot: str,
             user: dict = Depends(get_current_user)):
    """Live feedback as the operator types - no write, no fast-path change.
    Only /submit's own re-check of this exact comparison is ever trusted to
    actually log anything."""
    typed = entered_lot.strip()
    if not typed:
        raise HTTPException(status_code=400, detail="Nothing typed yet.")
    ctx = _lot_context(station, resin, cartridge_type)
    return LotCheckOut(result=_judge_lot(ctx["expected_lot"], ctx["expected_is_real"], typed))


# =============================================================================
# BULK / DRUM POUR MATH
# -----------------------------------------------------------------------------
# Ported from pouring_tab.py lines ~537-603, reusing bulk_pour.py's pure
# functions directly rather than re-deriving unit conversion in TypeScript -
# see bulk_pour.py's own docstring on why two copies of this arithmetic is
# how the tank and the form come to disagree about the same pour.
# =============================================================================
def _bulk_math(resin: str, station: str, containers: int, amount_each: float,
               unit: str, off_tank: bool, note: str) -> tuple[float, dict, str]:
    specs_df = crud.get_all_resin_specs_df("ALL")
    densities = (bulk_pour.density_map(specs_df.to_dict("records"), crud.container_litres)
                if not specs_df.empty else {})
    density = bulk_pour.resin_density(resin, densities)
    litres = bulk_pour.pour_litres(containers, amount_each, unit, density)
    if off_tank:
        verdict = bulk_pour.check_pour(litres)
    else:
        cap, remaining = bulk_vessel_state(resin, station)
        verdict = bulk_pour.check_pour(litres, capacity_l=cap, remaining_l=remaining)
    description = bulk_pour.describe_pour(containers, amount_each, unit, density, note,
                                          from_tank=not off_tank)
    return litres, verdict, description


@router.post("/bulk-preview", response_model=BulkPreviewOut)
def bulk_preview(resin: str, station: str, containers: int = 1, amount_each: float = 0.0,
                 unit: str = "L", off_tank: bool = False, note: str = "",
                 user: dict = Depends(get_current_user)):
    litres, verdict, description = _bulk_math(resin, station, containers, amount_each,
                                              unit, off_tank, note)
    return BulkPreviewOut(litres=litres, description=description,
                          blocked=verdict["blocked"], message=verdict["message"])


def _weight_spec_for(resin: str, cart_code: str):
    cart_matched = crud.get_all_resin_specs_df(cart_code)
    cart_matched = cart_matched[cart_matched["resin_name"] == resin] if not cart_matched.empty else cart_matched
    if not cart_matched.empty:
        return fill_weight.spec_from_row(cart_matched.iloc[0])
    all_specs = crud.get_all_resin_specs_df("ALL")
    matched = all_specs[all_specs["resin_name"] == resin]
    return fill_weight.spec_from_row(matched.iloc[0]) if not matched.empty else None


# =============================================================================
# SUBMIT - the actual pour log write
# -----------------------------------------------------------------------------
# Ported from pouring_tab.py lines ~672-803. The lot check is re-run here
# from scratch against server-side state (never trusting fast_confirm or any
# client-supplied "result") before crud.add_hourly_log writes the
# ProductionLog and its LotVerification row in one transaction.
# =============================================================================
@router.post("/submit", response_model=PourSubmitResponse)
async def submit(
    station: str = Form(...),
    cartridge_type: str = Form(...),
    resin: str = Form(...),
    entered_lot: str = Form(""),
    fast_confirm: bool = Form(False),
    mismatch_reason_kind: str = Form(""),
    mismatch_reason_detail: str = Form(""),
    mismatch_photo: UploadFile | None = File(None),
    is_bulk: bool = Form(False),
    bulk_containers: int = Form(1, ge=1),
    bulk_amount_each: float = Form(0.0, ge=0),
    bulk_unit: str = Form("L"),
    bulk_off_tank: bool = Form(False),
    bulk_note: str = Form(""),
    bottles_filled: int = Form(0, ge=0),
    scrap_empty: int = Form(0, ge=0),
    scrap_filled: int = Form(0, ge=0),
    check_weight_g: float | None = Form(None, ge=0),
    notes: str = Form(""),
    as_operator: str | None = Form(None),
    user: dict = Depends(get_current_user),
):
    operator_name = resolve_operator_name(user, as_operator)
    ctx = _lot_context(station, resin, cartridge_type)
    gate_applies, expected_lot, expected_is_real = (
        ctx["gate_applies"], ctx["expected_lot"], ctx["expected_is_real"])
    shift = user["shift"] or ""

    verification = None
    extra_note = ""
    lot_num = ctx["auto_lot"]

    if gate_applies:
        base_v = {
            "operator_name": operator_name, "pump_station": station, "shift": shift,
            "cartridge_type": cartridge_type, "resin_type": resin,
            "expected_lot": expected_lot if expected_is_real else None,
        }
        fast = _fast_path(user["id"], station, expected_lot, resin, cartridge_type, expected_is_real)
        if fast_confirm and fast:
            lot_num = expected_lot
            verification = dict(base_v, entered_lot=fast["entered"], result="verified", check_level="fast")
        else:
            typed = entered_lot.strip()
            if not typed:
                raise HTTPException(status_code=400, detail=f"Type the {ctx['words']['noun']}'s lot.")
            result = _judge_lot(expected_lot, expected_is_real, typed)
            reason_text = " — ".join(p for p in (mismatch_reason_kind, mismatch_reason_detail.strip()) if p)
            photo_filename = None
            if result == "mismatch":
                if not (mismatch_reason_kind and mismatch_reason_detail.strip()):
                    raise HTTPException(status_code=400,
                                        detail="Pick a reason and add details before logging a flagged pour.")
                if mismatch_photo is None or not mismatch_photo.filename:
                    raise HTTPException(status_code=400,
                                        detail=f"Photograph the {ctx['words']['noun']} bottom.")
                photo_filename = crud.save_lot_photo(await to_streamlit_like(mismatch_photo))
                extra_note = (f"⚠️ LOT MISMATCH — {ctx['words']['noun']} labelled L-{typed}, "
                             f"run expects {expected_lot}. {reason_text}")
            lot_num = typed if (result == "mismatch" or not expected_is_real) else expected_lot
            verification = dict(base_v, entered_lot=typed, result=result,
                                check_level="record" if result == "recorded" else "full",
                                reason=reason_text or None, photo_filename=photo_filename)
    else:
        lot_num = entered_lot.strip() or ctx["auto_lot"]

    bulk_litres = None
    units_for_log = bottles_filled
    if is_bulk:
        bulk_litres, verdict, _ = _bulk_math(resin, station, bulk_containers, bulk_amount_each,
                                             bulk_unit, bulk_off_tank, bulk_note)
        if verdict["blocked"]:
            raise HTTPException(status_code=400,
                                detail=verdict["message"] or "Enter an amount this vessel could actually have given out.")
        units_for_log = bulk_containers

    weight_reading = fill_weight.judge(check_weight_g, _weight_spec_for(resin, cartridge_type))
    log_notes = notes.strip()
    if extra_note:
        log_notes = f"{extra_note}\n{log_notes}".strip()

    try:
        matched_run = crud.add_hourly_log(
            operator_name=operator_name, pump_station=station, shift=shift,
            cartridge_type=cartridge_type, resin_type=resin, lot_number=lot_num,
            bottles=int(units_for_log), scrap_empty=int(scrap_empty), scrap_filled=int(scrap_filled),
            notes=log_notes, log_type="Hourly Bottle Count", verification=verification,
            weight=weight_reading, litres_poured=bulk_litres, pour_note=bulk_note,
            off_tank=bulk_off_tank,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not save the log: {str(e)[:160]}")

    if not bulk_off_tank:
        try:
            crud.adopt_vessel_resin(station, resin, operator=operator_name, shift=shift)
        except Exception:
            pass

    key = (user["id"], station)
    if gate_applies and verification is not None:
        if verification.get("result") == "verified":
            prev = _LOT_GATE_MEMORY.get(key) or {}
            _LOT_GATE_MEMORY[key] = {
                "expected": expected_lot, "resin": resin, "cart": cartridge_type,
                "entered": verification.get("entered_lot", ""), "ts": datetime.now(),
                "by": operator_name,
                "since_full": (prev.get("since_full", 0) + 1) if verification.get("check_level") == "fast" else 0,
            }
        else:
            _LOT_GATE_MEMORY.pop(key, None)

    log_id = None
    try:
        mine = crud.get_production_logs_df(operator=operator_name)
        mine = mine[mine["pump_station"] == station]
        if not mine.empty:
            log_id = int(mine.sort_values("id").iloc[-1]["id"])
    except Exception:
        pass

    messages = []
    if verification and verification.get("result") in ("mismatch", "expired"):
        messages.append("Logged and flagged for the manager — the lot did not check out.")
        crud.save_last_picks(operator_name, station, cartridge_type, resin)
    if weight_reading and weight_reading.get("status") in ("over", "under"):
        messages.append(
            f"Weight {weight_reading['measured']:.0f} g is outside the band for {resin} — "
            "recorded, and it shows on the manager's fill-weight view.")
    simple_mode = bool(crud.get_plant_settings().get("simple_mode", True))
    if matched_run:
        messages.append(f"Recorded {units_for_log} units of {resin}. Credited to your active run.")
        crud.save_last_picks(operator_name, station, cartridge_type, resin)
    elif simple_mode:
        messages.append(f"Recorded {units_for_log} units of {resin}.")
        crud.save_last_picks(operator_name, station, cartridge_type, resin)
    else:
        messages.append(
            f"Recorded {units_for_log} units of {resin} to Analytics — no active run matched "
            "this station/resin/lot, so it won't move a progress bar above.")

    if is_bulk and bulk_litres:
        landed = f"{bulk_litres:,.1f} L of {resin} into {bulk_note or 'containers'} at {station}"
    else:
        landed = f"{units_for_log} units of {resin} at {station}"

    weight_icon, weight_message = fill_weight.describe(weight_reading) if weight_reading else ("", "")
    realtime.notify()
    return PourSubmitResponse(ok=True, log_id=log_id, matched_run=matched_run,
                              weight_icon=weight_icon, weight_message=weight_message,
                              messages=messages, landed=landed)


@router.post("/undo", response_model=UndoResponse)
def undo(body: UndoRequest, user: dict = Depends(get_current_user)):
    ok, message = crud.undo_own_log(body.log_id, resolve_operator_name(user, body.as_operator))
    if ok:
        realtime.notify()
    return UndoResponse(ok=ok, message=message)
