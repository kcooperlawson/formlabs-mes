"""Log Management & Data Cleanup, ported from pages/Mgr_Log_Management.py:
finding and permanently removing bad or test production/downtime log
entries. Gated by manage_logs - "the one ability on this list that can
remove data" - for every route here, reads included, matching the
original's single page-level gate.

delete_production_log() already calls sync_all_runs_with_logs() internally
(see crud.py), which is what makes the page's own warning banner true:
deleting a log re-syncs whatever Work Order it was counted against.
"""
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import crud
from api.deps import require_ability
from api.schemas.log_management import (BulkDeleteResult, DowntimeLogFilters, DowntimeLogRow,
                                         DowntimeLogsOut, ProductionLogFilters, ProductionLogRow,
                                         ProductionLogsOut)
from resin_palette import resin_color

router = APIRouter(prefix="/log-management", tags=["log-management"])


def _filter_by_date(df: pd.DataFrame, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    if df.empty:
        return df
    date_obj = pd.to_datetime(df["date"]).dt.date
    if start_date:
        df = df[date_obj >= pd.Timestamp(start_date).date()]
        date_obj = pd.to_datetime(df["date"]).dt.date
    if end_date:
        df = df[date_obj <= pd.Timestamp(end_date).date()]
    return df


@router.get("/production", response_model=ProductionLogsOut)
def production_logs(start_date: str | None = None, end_date: str | None = None,
                    log_type: str = "All Types", pump_station: str = "All Pumps",
                    operator: str = "All Operators", limit: int = 100,
                    user: dict = Depends(require_ability("manage_logs"))):
    all_logs = crud.get_production_logs_df()
    if all_logs.empty:
        return ProductionLogsOut(
            filters=ProductionLogFilters(log_types=[], pumps=[], operators=[], min_date=None, max_date=None),
            total_matches=0, rows=[])

    date_obj = pd.to_datetime(all_logs["date"]).dt.date
    filters = ProductionLogFilters(
        log_types=sorted(all_logs["log_type"].dropna().unique().tolist()),
        pumps=sorted(all_logs["pump_station"].dropna().unique().tolist()),
        operators=sorted(all_logs["operator_name"].dropna().unique().tolist()),
        min_date=str(date_obj.min()), max_date=str(date_obj.max()))

    matches = _filter_by_date(all_logs, start_date, end_date)
    if log_type != "All Types":
        matches = matches[matches["log_type"] == log_type]
    if pump_station != "All Pumps":
        matches = matches[matches["pump_station"] == pump_station]
    if operator != "All Operators":
        matches = matches[matches["operator_name"] == operator]
    matches = matches.sort_values(by="timestamp", ascending=False)

    rows = [
        ProductionLogRow(
            id=int(r["id"]), timestamp=pd.Timestamp(r["timestamp"]).isoformat() + "Z",
            log_type=r["log_type"] or "", pump_station=r["pump_station"] or "",
            resin_type=(r["resin_type"] or None), resin_color=resin_color(r["resin_type"]) if r["resin_type"] else None,
            operator_name=r["operator_name"] or "", bottles_filled=int(r["bottles_filled"] or 0),
        )
        for _, r in matches.head(limit).iterrows()
    ]
    return ProductionLogsOut(filters=filters, total_matches=len(matches), rows=rows)


@router.delete("/production/{log_id}")
def delete_production(log_id: int, user: dict = Depends(require_ability("manage_logs"))):
    ok = crud.delete_production_log(log_id)
    if not ok:
        raise HTTPException(status_code=404, detail="No such production log.")
    return {"ok": True}


@router.post("/production/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete_production(start_date: str | None = None, end_date: str | None = None,
                           log_type: str = "All Types", pump_station: str = "All Pumps",
                           operator: str = "All Operators",
                           user: dict = Depends(require_ability("manage_logs"))):
    all_logs = crud.get_production_logs_df()
    matches = _filter_by_date(all_logs, start_date, end_date)
    if not matches.empty:
        if log_type != "All Types":
            matches = matches[matches["log_type"] == log_type]
        if pump_station != "All Pumps":
            matches = matches[matches["pump_station"] == pump_station]
        if operator != "All Operators":
            matches = matches[matches["operator_name"] == operator]
    deleted = sum(1 for log_id in matches["id"].tolist() if crud.delete_production_log(int(log_id)))
    return BulkDeleteResult(deleted=deleted)


@router.get("/downtime", response_model=DowntimeLogsOut)
def downtime_logs(start_date: str | None = None, end_date: str | None = None,
                  pump_station: str = "All Pumps", reason: str = "All Reasons", limit: int = 100,
                  user: dict = Depends(require_ability("manage_logs"))):
    all_dt = crud.get_downtime_logs_df()
    if all_dt.empty:
        return DowntimeLogsOut(
            filters=DowntimeLogFilters(pumps=[], reasons=[], min_date=None, max_date=None),
            total_matches=0, rows=[])

    date_obj = pd.to_datetime(all_dt["date"]).dt.date
    filters = DowntimeLogFilters(
        pumps=sorted(all_dt["pump_station"].dropna().unique().tolist()),
        reasons=sorted(all_dt["reason"].dropna().unique().tolist()),
        min_date=str(date_obj.min()), max_date=str(date_obj.max()))

    matches = _filter_by_date(all_dt, start_date, end_date)
    if pump_station != "All Pumps":
        matches = matches[matches["pump_station"] == pump_station]
    if reason != "All Reasons":
        matches = matches[matches["reason"] == reason]
    matches = matches.sort_values(by="timestamp", ascending=False)

    rows = [
        DowntimeLogRow(
            id=int(r["id"]), timestamp=pd.Timestamp(r["timestamp"]).isoformat() + "Z",
            pump_station=r["pump_station"] or "", reason=r["reason"] or "",
            duration_min=int(r["duration_min"] or 0), operator_name=r["operator_name"] or "",
        )
        for _, r in matches.head(limit).iterrows()
    ]
    return DowntimeLogsOut(filters=filters, total_matches=len(matches), rows=rows)


@router.delete("/downtime/{log_id}")
def delete_downtime(log_id: int, user: dict = Depends(require_ability("manage_logs"))):
    ok = crud.delete_downtime_log(log_id)
    if not ok:
        raise HTTPException(status_code=404, detail="No such downtime log.")
    return {"ok": True}


@router.post("/downtime/bulk-delete", response_model=BulkDeleteResult)
def bulk_delete_downtime(start_date: str | None = None, end_date: str | None = None,
                         pump_station: str = "All Pumps", reason: str = "All Reasons",
                         user: dict = Depends(require_ability("manage_logs"))):
    all_dt = crud.get_downtime_logs_df()
    matches = _filter_by_date(all_dt, start_date, end_date)
    if not matches.empty:
        if pump_station != "All Pumps":
            matches = matches[matches["pump_station"] == pump_station]
        if reason != "All Reasons":
            matches = matches[matches["reason"] == reason]
    deleted = sum(1 for log_id in matches["id"].tolist() if crud.delete_downtime_log(int(log_id)))
    return BulkDeleteResult(deleted=deleted)
