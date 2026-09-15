"""Fleet Production Progress & Work Order Dispatch, ported from
pages/Mgr_Assigned_Runs.py. The original page gates every action - dispatch,
progress, status, delete, custom-complete, sync - behind the same single
view_manager_cockpit check (no separate ability for writes), so every route
here does too, matching that exactly rather than inventing a stricter model.

get_assigned_runs_df(auto_sync=True) (the default) recomputes each run's
current_units from actual production logs on every call and auto-closes any
run that has reached its target - that recompute is what makes the +50/+100
buttons durable (see update_assigned_run_progress's own docstring) and is
preserved here unchanged.
"""
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import crud
from api.deps import require_ability
from api.schemas.assigned_runs import (AssignedRunOut, AssignedRunsOut, CompleteRequest,
                                       CreateRunRequest, ProgressRequest, ReactorOption,
                                       RunOptions, RunTotals, StatusRequest)
from resin_palette import resin_color

router = APIRouter(prefix="/assigned-runs", tags=["assigned-runs"])

STATUSES = ("Active", "Queued")


@router.get("/options", response_model=RunOptions)
def options(user: dict = Depends(require_ability("view_manager_cockpit"))):
    reactors_df = crud.get_all_reactors_df()
    users_df = crud.get_all_users_df()
    settings = crud.get_plant_settings()
    reactors = [ReactorOption(reactor_name=r["reactor_name"], max_capacity_l=int(r["max_capacity_l"]))
               for _, r in reactors_df.iterrows()] if not reactors_df.empty else []
    operators = users_df[users_df["role"] == "operator"]["full_name"].tolist() if not users_df.empty else []
    packers = users_df[users_df["role"] == "packer"]["full_name"].tolist() if not users_df.empty else []
    return RunOptions(
        reactors=reactors, pumps=crud.get_active_pumps(), operators=operators, packers=packers,
        pump_count=len(crud.get_all_pumps_df()), enable_packing=bool(settings.get("enable_packing", True)))


def _row_out(r) -> AssignedRunOut:
    return AssignedRunOut(
        id=int(r["id"]), run_type=r["run_type"], status=r["status"],
        reactor_id=r["reactor_id"] or "", reactor_size_l=int(r["reactor_size_l"] or 0),
        resin_type=r["resin_type"] or "", resin_color=resin_color(r["resin_type"]),
        cartridge_type=r["cartridge_type"] or "", target_units=int(r["target_units"]),
        current_units=int(r["current_units"]), assigned_operator=r["assigned_operator"] or "",
        pump_station=r["pump_station"] or "", lot_number=str(r["lot_number"] or ""),
        notes=r["notes"] or "", created_at=pd.Timestamp(r["created_at"]).isoformat() + "Z",
    )


@router.get("", response_model=AssignedRunsOut)
def list_runs(user: dict = Depends(require_ability("view_manager_cockpit"))):
    df = crud.get_assigned_runs_df()
    runs = [_row_out(r) for _, r in df.iterrows()] if not df.empty else []

    total_target = int(df["target_units"].sum()) if not df.empty else 0
    total_actual = int(df["current_units"].sum()) if not df.empty else 0
    fleet_pct = round(total_actual / total_target * 100, 1) if total_target > 0 else 0.0
    active_count = int(df["status"].isin(["Active", "Pouring"]).sum()) if not df.empty else 0
    queued_count = int((df["status"] == "Queued").sum()) if not df.empty else 0
    done_count = int((df["status"] == "Done").sum()) if not df.empty else 0
    pumps_in_use = df["pump_station"].nunique() if not df.empty else 0

    totals = RunTotals(
        total_target=total_target, total_actual=total_actual, fleet_pct=fleet_pct,
        active_count=active_count, queued_count=queued_count, done_count=done_count,
        pumps_configured=len(crud.get_all_pumps_df()), pumps_in_use=int(pumps_in_use),
        active_operators_count=len(crud.get_active_operators()),
    )
    return AssignedRunsOut(runs=runs, totals=totals)


@router.post("", status_code=201)
def create_run(body: CreateRunRequest, user: dict = Depends(require_ability("view_manager_cockpit"))):
    if body.status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {STATUSES}")
    auto_detected = crud.create_assigned_run(
        reactor_id=body.reactor_id, reactor_size_l=body.reactor_size_l, resin_type=body.resin_type,
        cartridge_type=body.cartridge_type, target_units=body.target_units,
        assigned_operator=body.assigned_operator, pump_station=body.assigned_pump,
        lot_number=body.lot_number, notes=body.notes, status=body.status, run_type=body.run_type)
    return {"ok": True, "auto_detected_units": auto_detected}


@router.post("/sync")
def sync(user: dict = Depends(require_ability("view_manager_cockpit"))):
    crud.sync_all_runs_with_logs()
    return {"ok": True}


@router.post("/{run_id}/progress")
def progress(run_id: int, body: ProgressRequest, user: dict = Depends(require_ability("view_manager_cockpit"))):
    crud.update_assigned_run_progress(run_id, body.delta, operator_name=user["full_name"])
    return {"ok": True}


@router.post("/{run_id}/status")
def set_status(run_id: int, body: StatusRequest, user: dict = Depends(require_ability("view_manager_cockpit"))):
    if body.status not in STATUSES:
        raise HTTPException(status_code=400, detail=f"status must be one of {STATUSES}")
    crud.update_run_status(run_id, body.status)
    return {"ok": True}


@router.post("/{run_id}/complete")
def complete(run_id: int, body: CompleteRequest, user: dict = Depends(require_ability("view_manager_cockpit"))):
    df = crud.get_assigned_runs_df(auto_sync=False)
    match = df[df["id"] == run_id]
    if match.empty:
        raise HTTPException(status_code=404, detail="No such work order.")
    lot_number = str(match.iloc[0]["lot_number"] or "")
    ok = crud.complete_run_with_custom_total(run_id, body.final_units)
    if not ok:
        raise HTTPException(status_code=404, detail="No such work order.")
    if lot_number:
        crud.reconcile_pouring_to_packing(lot_number, body.final_units)
    return {"ok": True}


@router.delete("/{run_id}")
def delete_run(run_id: int, user: dict = Depends(require_ability("view_manager_cockpit"))):
    ok = crud.delete_assigned_run(run_id)
    if not ok:
        raise HTTPException(status_code=404, detail="No such work order.")
    return {"ok": True}
