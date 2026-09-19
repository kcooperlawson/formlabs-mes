"""Click any lot, run, pump, operator, resin, reactor or total and see what
it is made of. One endpoint for all of them - see drill.py for why.

An operator can drill into anything, but only ever sees their own rows: the
operator filter is forced to them, the same way every other operator screen
is scoped. Managers and admins see the floor.
"""
from datetime import date, timezone

from fastapi import APIRouter, Depends, HTTPException

import crud
import drill as _drill
from api.deps import get_current_user, resolve_operator_name

router = APIRouter(prefix="/drill", tags=["drill"])


def _iso(value):
    if value is None:
        return None
    if getattr(value, "tzinfo", None) is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _local(value):
    """Batch times are written as plant-local wall-clock time (see
    api/routers/batch_history.py), so they go out without an offset and the
    browser reads them as local - marking them UTC would shift them by hours."""
    return value.isoformat() if value else None


def _day(value: str, name: str):
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"{name}: {value!r} isn't a date (YYYY-MM-DD).")


@router.get("")
def drill(lot: str = "", run_id: int = 0, pump: str = "", operator: str = "", resin: str = "",
          reactor: str = "", shift: str = "", date_from: str = "", date_to: str = "",
          as_operator: str = "", user: dict = Depends(get_current_user)):
    settings = crud.get_plant_settings()
    is_management = (user.get("role", "") == "manager"
                     or crud.can_administer(user.get("role", ""), settings.get("simple_mode", True)))
    scope = "everyone"
    if not is_management or as_operator:
        operator = resolve_operator_name(user, as_operator)
        scope = "self"

    if not any((lot, run_id, pump, operator, resin, reactor, date_from, date_to)):
        raise HTTPException(status_code=400, detail="Say what to look at - a lot, run, pump, operator, resin, reactor or a date.")

    out = _drill.drill({"lot": lot.strip(), "run_id": run_id or None, "pump": pump.strip(),
                        "operator": operator.strip(), "resin": resin.strip(), "reactor": reactor.strip(),
                        "shift": shift.strip(), "date_from": _day(date_from, "date_from"),
                        "date_to": _day(date_to, "date_to")})
    if run_id and out["run"] is None:
        raise HTTPException(status_code=404, detail=f"There is no run #{run_id}.")

    s = out["summary"]
    run, vessel = out["run"], out["reactor"]
    return {
        "scope": scope,
        "filters": {k: (v.isoformat() if isinstance(v, date) else v) for k, v in out["filters"].items()},
        "summary": {**s, "first_at": _iso(s["first_at"]), "last_at": _iso(s["last_at"])},
        "truncated": out["truncated"],
        "run": None if run is None else {
            "id": run.id, "resin_type": run.resin_type, "cartridge_type": run.cartridge_type,
            "pump_station": run.pump_station, "lot_number": run.lot_number or "",
            "assigned_operator": run.assigned_operator, "target_units": run.target_units or 0,
            "current_units": run.current_units or 0, "status": run.status, "reactor_id": run.reactor_id,
            "created_at": _iso(run.created_at), "notes": run.notes or "", "run_type": run.run_type or "",
        },
        "reactor": None if vessel is None else {
            "name": vessel.reactor_name, "capacity_l": vessel.max_capacity_l, "status": vessel.status,
            "current_resin": vessel.current_resin or "", "assigned_pump": vessel.assigned_pump or "",
            "asset_tag": vessel.asset_tag or "", "bay_marker": vessel.bay_marker or "",
        },
        "logs": [{
            "id": r.id, "timestamp": _iso(r.timestamp), "date": r.date.isoformat() if r.date else None,
            "log_type": r.log_type, "operator_name": r.operator_name, "pump_station": r.pump_station,
            "shift": r.shift, "resin_type": r.resin_type or "", "cartridge_type": r.cartridge_type or "",
            "lot_number": r.lot_number or "", "bottles": int(r.bottles_filled or 0),
            "litres": round(crud.log_litres(r.bottles_filled, r.cartridge_type, r.litres_poured), 2),
            "scrap_empty": int(r.scrap_empty or 0), "scrap_filled": int(r.scrap_filled or 0),
            "weight_status": r.weight_status or "", "check_weight_g": r.check_weight_g,
            "verify_status": r.verify_status or "", "notes": r.notes or "", "pour_note": r.pour_note or "",
        } for r in out["logs"]],
        "runs": [{
            "id": r.id, "resin_type": r.resin_type, "pump_station": r.pump_station,
            "lot_number": r.lot_number or "", "assigned_operator": r.assigned_operator,
            "target_units": r.target_units or 0, "current_units": r.current_units or 0,
            "status": r.status, "created_at": _iso(r.created_at),
        } for r in out["runs"]],
        "batches": [{
            "id": b.id, "reactor_name": b.reactor_name, "resin_type": b.resin_type or "",
            "lot_number": b.lot_number or "", "pump_station": b.pump_station or "",
            "filled_at": _local(b.filled_at), "emptied_at": _local(b.emptied_at),
            "qc_result": b.qc_result or "", "qc_sent_at": _local(b.qc_sent_at),
            "qc_result_at": _local(b.qc_result_at), "qc_note": b.qc_note or "",
        } for b in out["batches"]],
        "verifications": [{
            "id": v.id, "timestamp": _iso(v.timestamp), "operator_name": v.operator_name,
            "pump_station": v.pump_station, "expected_lot": v.expected_lot or "",
            "entered_lot": v.entered_lot or "", "result": v.result, "check_level": v.check_level or "",
            "expiry_status": v.expiry_status or "", "reason": v.reason or "",
            "photo_filename": v.photo_filename or "",
        } for v in out["verifications"]],
        "downtime": [{
            "id": d.id, "timestamp": _iso(d.timestamp), "operator_name": d.operator_name,
            "pump_station": d.pump_station, "shift": d.shift, "reason": d.reason,
            "duration_min": int(d.duration_min or 0), "notes": d.notes or "",
        } for d in out["downtime"]],
        "downtime_min": out["downtime_min"],
        "audits": [{
            "id": a.id, "timestamp": _iso(a.timestamp), "operator_name": a.operator_name,
            "pump_station": a.pump_station, "shift": a.shift, "audit_type": a.audit_type,
            "is_spill": a.is_spill == "Yes", "image_filename": a.image_filename or "", "notes": a.notes or "",
        } for a in out["audits"]],
    }
