"""Historical Plant Analytics, ported from pages/Mgr_Historical.py: output,
scrap and yield trends over a time horizon, filterable by resin and
operator. Operator identity resolution (preferring each operator_id's
current full_name so a mid-history rename shows one entry, not two) is
copied verbatim from the original page.
"""
from datetime import date, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import crud
from api.deps import require_ability
from api.schemas.historical import (HistoricalFilters, HistoricalOut,
                                    HistoricalTotals, OperatorOutput, TrendPoint)

router = APIRouter(prefix="/historical", tags=["historical"])

HORIZONS = ("7d", "30d", "ytd", "all")


@router.get("", response_model=HistoricalOut)
def historical(horizon: str = "7d", resin: str = "All Resins", operator: str = "All Operators",
              user: dict = Depends(require_ability("view_manager_cockpit"))):
    if horizon not in HORIZONS:
        raise HTTPException(status_code=400, detail=f"horizon must be one of {HORIZONS}")

    df_logs = crud.get_production_logs_df()
    users_df = crud.get_all_users_df()
    id_to_name = dict(zip(users_df["id"], users_df["full_name"])) if not users_df.empty else {}
    name_to_id = {v: k for k, v in id_to_name.items()}

    if not df_logs.empty:
        resolved_ids = df_logs["operator_id"].dropna().unique().tolist()
        resolved_names = sorted({id_to_name[i] for i in resolved_ids if i in id_to_name})
        unresolved_names = sorted(
            df_logs[df_logs["operator_id"].isna()]["operator_name"].dropna().unique().tolist())
        operator_options = resolved_names + unresolved_names
        resin_options = sorted(df_logs["resin_type"].dropna().unique().tolist())
    else:
        operator_options = []
        resin_options = []
    filters = HistoricalFilters(resins=resin_options, operators=operator_options)

    today_d = date.today()
    start_date_filter = None
    if horizon == "7d":
        start_date_filter = today_d - timedelta(days=7)
    elif horizon == "30d":
        start_date_filter = today_d - timedelta(days=30)
    elif horizon == "ytd":
        start_date_filter = date(today_d.year, 1, 1)

    selected_operator_id = name_to_id.get(operator) if operator != "All Operators" else None
    selected_operator_name = operator if (operator != "All Operators" and selected_operator_id is None) else None

    hist_df = crud.get_production_logs_df(
        start_date=start_date_filter, end_date=today_d, resin=resin,
        operator=selected_operator_name, operator_id=selected_operator_id)

    if hist_df.empty:
        return HistoricalOut(
            filters=filters,
            totals=HistoricalTotals(total_poured=0, total_packed=0, total_scrap=0, yield_pct=100.0),
            trend=[], by_operator=[])

    pour_df = hist_df[hist_df["log_type"] == "Hourly Bottle Count"]
    pack_df = hist_df[hist_df["log_type"] == "Packing Count"]
    total_poured = int(pour_df["bottles_filled"].sum()) if not pour_df.empty else 0
    total_packed = int(pack_df["bottles_filled"].sum()) if not pack_df.empty else 0
    total_scrap = int(pour_df["scrap_empty"].sum() + pour_df["scrap_filled"].sum()) if not pour_df.empty else 0
    yield_pct = (round(total_poured / (total_poured + total_scrap) * 100, 1)
                if (total_poured + total_scrap) > 0 else 100.0)
    totals = HistoricalTotals(total_poured=total_poured, total_packed=total_packed,
                              total_scrap=total_scrap, yield_pct=yield_pct)

    trend: list[TrendPoint] = []
    by_operator: list[OperatorOutput] = []
    if not pour_df.empty:
        pour_df = pour_df.copy()
        pour_df["date_str"] = pd.to_datetime(pour_df["date"]).dt.strftime("%Y-%m-%d")
        trend_df = pour_df.groupby("date_str")["bottles_filled"].sum().reset_index()
        trend = [TrendPoint(date=row["date_str"], bottles_filled=int(row["bottles_filled"]))
                for _, row in trend_df.iterrows()]

        pour_df["display_operator"] = pour_df.apply(
            lambda r: id_to_name.get(r.get("operator_id"), r["operator_name"]), axis=1)
        op_df = (pour_df.groupby("display_operator")["bottles_filled"].sum()
                .reset_index().sort_values("bottles_filled", ascending=False))
        by_operator = [OperatorOutput(operator=row["display_operator"], bottles_filled=int(row["bottles_filled"]))
                      for _, row in op_df.iterrows()]

    return HistoricalOut(filters=filters, totals=totals, trend=trend, by_operator=by_operator)
