"""Batch History, ported from pages/Mgr_Batch_History.py: reactor dwell time
and QC turnaround, plus the QC-entry form that used to live on the reactor
page (moved here in the original so the numbers and the data entry that
feeds them sit on one screen). See that page's own module docstring for why
dwell time comes from "marked empty or next changeover, whichever happens
first" and why QC timestamps are typed rather than stamped.

Unlike lot_verification.py, these are naive local datetimes throughout
(crud.get_batches/set_batch_qc use datetime.now(), not utcnow) - serialized
here with a bare isoformat(), no "Z", so the browser parses them back as
local time the same way the original page displayed them directly.
"""
from datetime import datetime, timedelta
from statistics import mean

from fastapi import APIRouter, Depends, HTTPException

import crud
from api.deps import require_ability
from api.schemas.batch_history import (BatchHistoryOut, BatchRow, BatchTotals,
                                       DwellByVessel, OutAtQc, QcTrendPoint,
                                       SetBatchQcRequest)

router = APIRouter(prefix="/batch-history", tags=["batch-history"])

ALLOWED_WINDOWS = (7, 14, 30, 90, 365)


def _iso(dt) -> str | None:
    return dt.isoformat() if dt else None


@router.get("", response_model=BatchHistoryOut)
def batch_history(days: int = 30, user: dict = Depends(require_ability("view_manager_cockpit"))):
    if days not in ALLOWED_WINDOWS:
        raise HTTPException(status_code=400, detail=f"days must be one of {ALLOWED_WINDOWS}")

    rows = crud.get_batches(since=datetime.now() - timedelta(days=days), limit=800)
    can_manage_qc = crud.user_can(user["id"], user["role"], "manage_qc")

    if not rows:
        return BatchHistoryOut(
            totals=BatchTotals(fillings_in_window=0, sitting_now=0, waiting_qc=0,
                              avg_qc_turnaround_h=None, avg_time_in_vessel_h=None,
                              longest_sitting_h=None, longest_qc_wait_h=None, no_qc_recorded=0),
            dwell_by_vessel=[], qc_trend=[], out_at_qc=[], batches=[], can_manage_qc=can_manage_qc)

    open_batches = [b for b in rows if b["open"]]
    at_qc = [b for b in rows if b["qc_open"]]
    done = [b for b in rows if not b["qc_open"] and b["hours_at_qc"] is not None]
    closed = [b for b in rows if not b["open"]]
    no_qc_recorded = [b for b in open_batches if b["qc_result"] == "" and not b["qc_open"]]

    totals = BatchTotals(
        fillings_in_window=len(rows),
        sitting_now=len(open_batches),
        waiting_qc=len(at_qc),
        avg_qc_turnaround_h=round(mean(b["hours_at_qc"] for b in done), 1) if done else None,
        avg_time_in_vessel_h=round(mean(b["hours_in_reactor"] for b in closed), 1) if closed else None,
        longest_sitting_h=round(max(b["hours_in_reactor"] for b in open_batches), 0) if open_batches else None,
        longest_qc_wait_h=round(max(b["hours_at_qc"] for b in at_qc), 0) if at_qc else None,
        no_qc_recorded=len(no_qc_recorded),
    )

    dwell_totals: dict[str, list[float]] = {}
    for b in closed:
        dwell_totals.setdefault(b["reactor_name"], []).append(b["hours_in_reactor"])
    dwell_by_vessel = sorted(
        (DwellByVessel(reactor_name=name, avg_hours=round(mean(hrs), 1)) for name, hrs in dwell_totals.items()),
        key=lambda d: d.avg_hours)

    trend_totals: dict[str, list[float]] = {}
    for b in done:
        day = b["qc_result_at"].date().isoformat()
        trend_totals.setdefault(day, []).append(b["hours_at_qc"])
    qc_trend = sorted(
        (QcTrendPoint(day=day, avg_hours=round(mean(hrs), 1)) for day, hrs in trend_totals.items()),
        key=lambda t: t.day)

    out_at_qc = sorted(
        (OutAtQc(id=b["id"], reactor_name=b["reactor_name"], resin_type=b["resin_type"] or "resin not recorded",
                hours_at_qc=round(b["hours_at_qc"], 0)) for b in at_qc),
        key=lambda o: o.hours_at_qc, reverse=True)

    batches = [
        BatchRow(
            id=b["id"], reactor_name=b["reactor_name"], resin_type=b["resin_type"],
            filled_at=_iso(b["filled_at"]), emptied_at=_iso(b["emptied_at"]),
            hours_in_reactor=b["hours_in_reactor"],
            qc_sent_at=_iso(b["qc_sent_at"]), qc_result_at=_iso(b["qc_result_at"]),
            hours_at_qc=b["hours_at_qc"], qc_result=b["qc_result"] or "",
            qc_note=b["qc_note"] or "", qc_by=b["qc_by"] or "",
            open=b["open"], qc_open=b["qc_open"],
        )
        for b in rows
    ]

    return BatchHistoryOut(totals=totals, dwell_by_vessel=dwell_by_vessel, qc_trend=qc_trend,
                           out_at_qc=out_at_qc, batches=batches, can_manage_qc=can_manage_qc)


@router.post("/{batch_id}/qc")
def save_qc(batch_id: int, body: SetBatchQcRequest, user: dict = Depends(require_ability("manage_qc"))):
    try:
        sent_at = datetime.fromisoformat(body.sent_at)
        result_at = datetime.fromisoformat(body.result_at) if body.result_at else None
    except ValueError:
        raise HTTPException(status_code=422, detail="Timestamps must be ISO 8601.")
    ok, msg = crud.set_batch_qc(batch_id, sent_at=sent_at, result_at=result_at,
                                result=body.result, note=body.note, by=user["full_name"])
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}
