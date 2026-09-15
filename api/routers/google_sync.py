"""External Reporting & Google Cloud Sync, ported from
pages/Mgr_Google_Sync.py: link a destination sheet (via its own Apps
Script - a spreadsheet has no inbox, see sheet_sync.py's own docstring for
why), preview/export the payload as a file, or push it straight to a
linked sheet. Gated by export_data throughout, matching the original's
single page-level check.

sheet_sync.py is pure functions (URL classification, horizon math, the
Apps Script text, response diagnosis) with zero Streamlit or DB coupling,
so it's reused here exactly as crud.py's business logic is - nothing in
this router re-implements anything that module already does correctly.
"""
import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

import crud
import sheet_sync
from api.deps import require_ability
from api.schemas.google_sync import (AddTargetRequest, ClassifyUrlOut, ExportPreviewOut,
                                     PushRequest, PushResult, SheetTargetOut, TestResult,
                                     UpdateTargetRequest)

router = APIRouter(prefix="/google-sync", tags=["google-sync"])

EXPORT_MODES = ("📊 Aggregated Calculated Metrics (KPI Summary)", "📋 Raw Production Audit Stream")


def _is_admin(user: dict) -> bool:
    return user["role"] == "admin"


def _owner_id(row: dict) -> int | None:
    """owner_user_id, NaN-safe.

    A legacy row (the pre-database single .env webhook, carried over by
    migration 0013 with no owner) has a real SQL NULL here - which
    pandas.DataFrame(list_of_dicts) reads back as float NaN, not None, the
    same trap fixed in api/routers/reactors.py's _s(). visible_targets()
    tolerates that already (`owner is not None` never matches a NaN
    either way), but Pydantic's `int | None` rejects NaN outright.
    """
    owner = row.get("owner_user_id")
    if owner is None or (isinstance(owner, float) and owner != owner):
        return None
    return int(owner)


def _target_out(row: dict, user: dict) -> SheetTargetOut:
    owner = _owner_id(row)
    editable = _is_admin(user) or (owner is not None and owner == user["id"])
    return SheetTargetOut(
        id=int(row["id"]), name=row["name"], webhook_url=row["webhook_url"],
        owner_user_id=owner, owner_name=row.get("owner_name") or "",
        is_shared=bool(row.get("is_shared")), label=sheet_sync.target_label(row),
        last_sync_text=sheet_sync.last_sync_text(row.get("last_sync_at"), row.get("last_status")),
        editable=editable,
    )


def _visible_rows(user: dict) -> list[dict]:
    all_targets = crud.get_sheet_targets_df()
    rows = all_targets.to_dict("records") if not all_targets.empty else []
    return sheet_sync.visible_targets(rows, user["id"], _is_admin(user))


@router.get("/targets", response_model=list[SheetTargetOut])
def list_targets(user: dict = Depends(require_ability("export_data"))):
    return [_target_out(r, user) for r in _visible_rows(user)]


@router.get("/classify-url", response_model=ClassifyUrlOut)
def classify_url(url: str = "", user: dict = Depends(require_ability("export_data"))):
    return ClassifyUrlOut(**sheet_sync.classify_url(url))


@router.post("/targets", status_code=201, response_model=SheetTargetOut)
def add_target(body: AddTargetRequest, user: dict = Depends(require_ability("export_data"))):
    verdict = sheet_sync.classify_url(body.url)
    if not verdict["ok"]:
        raise HTTPException(status_code=400, detail=verdict["message"])
    ok, msg = crud.add_sheet_target(body.name, verdict["url"], user["id"], user["full_name"], body.is_shared)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    rows = _visible_rows(user)
    row = next(r for r in rows if r["name"] == body.name.strip() and r.get("owner_user_id") == user["id"])
    return _target_out(row, user)


def _find_target(target_id: int, user: dict) -> dict:
    rows = _visible_rows(user)
    row = next((r for r in rows if int(r["id"]) == target_id), None)
    if not row:
        raise HTTPException(status_code=404, detail="No such sheet destination.")
    return row


def _require_editable(row: dict, user: dict):
    owner = row.get("owner_user_id")
    if not (_is_admin(user) or (owner is not None and owner == user["id"])):
        raise HTTPException(status_code=403, detail="This sheet was shared by somebody else, so only they can change it.")


@router.put("/targets/{target_id}", response_model=SheetTargetOut)
def update_target(target_id: int, body: UpdateTargetRequest, user: dict = Depends(require_ability("export_data"))):
    row = _find_target(target_id, user)
    _require_editable(row, user)
    ok = crud.update_sheet_target(target_id, name=body.name, webhook_url=body.webhook_url, is_shared=body.is_shared)
    if not ok:
        raise HTTPException(status_code=404, detail="No such sheet destination.")
    return _target_out(_find_target(target_id, user), user)


@router.delete("/targets/{target_id}")
def delete_target(target_id: int, user: dict = Depends(require_ability("export_data"))):
    row = _find_target(target_id, user)
    _require_editable(row, user)
    crud.delete_sheet_target(target_id)
    return {"ok": True}


@router.post("/targets/{target_id}/test", response_model=TestResult)
def test_target(target_id: int, user: dict = Depends(require_ability("export_data"))):
    row = _find_target(target_id, user)
    try:
        import requests
        r = requests.post(row["webhook_url"], json={"ping": True}, timeout=30)
        verdict = sheet_sync.diagnose_response(r.status_code, r.text, row["webhook_url"])
        if verdict["ok"]:
            named = verdict.get("sheet")
            msg = f'Answered from "{named}". This sheet is reachable and the script is live.' if named \
                else "Answered. This sheet is reachable and the script is live."
            if verdict["message"]:
                msg += " " + verdict["message"]
            return TestResult(ok=True, message=msg)
        return TestResult(ok=False, message=verdict["message"])
    except Exception as exc:
        return TestResult(ok=False, message=f"Could not reach it: {str(exc)[:200]}")


def _build_export_df(export_mode: str, horizon: str) -> pd.DataFrame:
    df_logs = crud.get_production_logs_df()
    df_logs = sheet_sync.filter_by_horizon(df_logs, horizon)

    if export_mode == EXPORT_MODES[0]:  # Aggregated
        if df_logs.empty:
            return pd.DataFrame()
        calc_df = df_logs.copy()
        calc_df["date_str"] = pd.to_datetime(calc_df["date"]).dt.strftime("%Y-%m-%d")

        def get_row_liters(r):
            b_count = float(r.get("bottles_filled", 0) or 0)
            c_type = str(r.get("cartridge_type", "V2")).strip().upper()
            return crud.log_litres(b_count, c_type, r.get("litres_poured"))

        calc_df["liters_calc"] = calc_df.apply(get_row_liters, axis=1)
        calc_df["total_scrap"] = calc_df["scrap_empty"].fillna(0) + calc_df["scrap_filled"].fillna(0)

        summary_df = calc_df.groupby(
            ["date_str", "shift", "resin_type", "cartridge_type", "operator_name", "pump_station"]
        ).agg(
            Total_Poured_Units=("bottles_filled", lambda x: x[calc_df.loc[x.index, "log_type"] == "Hourly Bottle Count"].sum()),
            Total_Packed_Units=("bottles_filled", lambda x: x[calc_df.loc[x.index, "log_type"] == "Packing Count"].sum()),
            Volume_Output_Liters=("liters_calc", lambda x: x[calc_df.loc[x.index, "log_type"] == "Hourly Bottle Count"].sum()),
            Total_Scrap_Units=("total_scrap", "sum"),
            Log_Count=("id", "count"),
        ).reset_index()

        summary_df["Quality FPY (%)"] = (summary_df["Total_Poured_Units"] / (summary_df["Total_Poured_Units"] + summary_df["Total_Scrap_Units"]) * 100).fillna(100.0).round(2)
        summary_df["Scrap Rate (%)"] = (summary_df["Total_Scrap_Units"] / (summary_df["Total_Poured_Units"] + summary_df["Total_Scrap_Units"]) * 100).fillna(0.0).round(2)
        summary_df["Pending Floor WIP"] = (summary_df["Total_Poured_Units"] - summary_df["Total_Packed_Units"]).clip(lower=0)
        summary_df["Est Skids Built"] = (summary_df["Total_Packed_Units"] / 500.0).round(2)

        summary_df.rename(columns={
            "date_str": "Date", "shift": "Shift", "resin_type": "Resin Formulation",
            "cartridge_type": "Container Format", "operator_name": "Operator Name",
            "pump_station": "Pump Station", "Total_Poured_Units": "Units Poured",
            "Total_Packed_Units": "Units Packed", "Volume_Output_Liters": "Volume Output (Liters)",
            "Total_Scrap_Units": "Scrap Reject Units",
        }, inplace=True)
        return summary_df

    # Raw stream
    if df_logs.empty:
        return pd.DataFrame()
    return df_logs.drop(columns=[c for c in ["date_obj", "date_str"] if c in df_logs.columns]).copy()


@router.get("/export-preview", response_model=ExportPreviewOut)
def export_preview(export_mode: str, horizon: str, user: dict = Depends(require_ability("export_data"))):
    if export_mode not in EXPORT_MODES:
        raise HTTPException(status_code=400, detail=f"export_mode must be one of {EXPORT_MODES}")
    if horizon not in sheet_sync.HORIZONS:
        raise HTTPException(status_code=400, detail=f"horizon must be one of {list(sheet_sync.HORIZONS)}")
    df = _build_export_df(export_mode, horizon)
    if df.empty:
        return ExportPreviewOut(columns=[], rows=[], row_count=0)
    safe = df.astype(object).where(pd.notnull(df), None)
    return ExportPreviewOut(columns=list(df.columns), rows=safe.to_dict("records"), row_count=len(df))


@router.get("/export.xlsx")
def export_xlsx(export_mode: str, horizon: str, columns: str = "",
               user: dict = Depends(require_ability("export_data"))):
    if not sheet_sync.excel_available():
        raise HTTPException(status_code=409, detail="Excel export needs the openpyxl package, which is not installed here.")
    df = _build_export_df(export_mode, horizon)
    cols = [c for c in columns.split(",") if c] or list(df.columns)
    df = df[cols] if not df.empty else df
    sheet_name = "KPI Summary" if "Aggregated" in export_mode else "Raw Audit Logs"
    data = sheet_sync.workbook_bytes(df, sheet_name)
    filename = sheet_sync.export_filename(export_mode, horizon, "xlsx")
    return Response(
        content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.post("/push", response_model=PushResult)
def push(body: PushRequest, user: dict = Depends(require_ability("export_data"))):
    if body.export_mode not in EXPORT_MODES:
        raise HTTPException(status_code=400, detail=f"export_mode must be one of {EXPORT_MODES}")
    if body.horizon not in sheet_sync.HORIZONS:
        raise HTTPException(status_code=400, detail=f"horizon must be one of {list(sheet_sync.HORIZONS)}")
    target = _find_target(body.target_id, user)

    df = _build_export_df(body.export_mode, body.horizon)
    if not body.columns:
        raise HTTPException(status_code=400, detail="Please select at least one metric column to export.")
    if df.empty:
        raise HTTPException(status_code=400, detail="Nothing to send for that time horizon. Widen the scope, or check that production has been logged.")

    final_df = df[body.columns].copy().astype(str)
    payload = final_df.to_dict(orient="records")
    target_tab = "KPI Summary" if "Aggregated" in body.export_mode else "Raw Audit Logs"
    wrapped = {"sheet_name": target_tab, "data": payload}

    try:
        import requests
        response = requests.post(target["webhook_url"], json=wrapped, timeout=120)
        verdict = sheet_sync.diagnose_response(response.status_code, response.text, target["webhook_url"], expect_rows=len(final_df))
        if verdict["ok"]:
            wrote = verdict["rows"] if verdict["rows"] is not None else len(final_df)
            crud.record_sheet_sync(target["id"], "ok", int(wrote))
            return PushResult(ok=True, message=verdict["message"], rows=int(wrote),
                              tab=verdict.get("tab") or target_tab, sheet=verdict.get("sheet") or target["name"],
                              url=verdict.get("url"))
        crud.record_sheet_sync(target["id"], f"{verdict['level']} (HTTP {response.status_code})", 0)
        return PushResult(ok=False, message=verdict["message"], url=verdict.get("url"))
    except Exception as exc:
        crud.record_sheet_sync(target["id"], str(exc)[:180], 0)
        return PushResult(ok=False, message=f"Transmission Error: {str(exc)[:200]}")
