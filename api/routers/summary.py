"""My Shift Summary - a read-only, on-demand personal breakdown, ported
from pages/operator_form/summary_tab.py. Always scoped to the signed-in
operator/packer's own logs (the original has no plant-wide variant at all -
that's Manager Cockpit's job, behind view_manager_cockpit, a later phase).

Nothing here is written anywhere; it's aggregated fresh from today's
already-submitted logs on every call, same as the original's own comment
says of itself.
"""
from datetime import date

from fastapi import APIRouter, Depends

import crud
from api.deps import get_current_user, resolve_operator_name
from api.schemas.summary import HourlyPoint, ResinPoint, ShiftSummaryOut

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("/today", response_model=ShiftSummaryOut)
def today(as_operator: str | None = None, user: dict = Depends(get_current_user)):
    today_d = date.today()
    df_today = crud.get_production_logs_df(start_date=today_d, end_date=today_d,
                                           operator=resolve_operator_name(user, as_operator))
    if df_today.empty:
        return ShiftSummaryOut(has_logs_today=False, units=0, scrap=0, yield_pct=100.0,
                               logs_submitted=0, has_output_logs=False)

    log_type_wanted = "Packing Count" if user["role"] == "packer" else "Hourly Bottle Count"
    df_mine = df_today[df_today["log_type"] == log_type_wanted]

    units = int(df_mine["bottles_filled"].sum()) if not df_mine.empty else 0
    scrap = int(df_mine["scrap_empty"].sum() + df_mine["scrap_filled"].sum()) if not df_mine.empty else 0
    yield_pct = (units / (units + scrap) * 100) if (units + scrap) > 0 else 100.0

    if df_mine.empty:
        return ShiftSummaryOut(has_logs_today=True, units=0, scrap=0, yield_pct=100.0,
                               logs_submitted=int(len(df_today)), has_output_logs=False)

    hourly = df_mine.copy()
    hourly["hour"] = hourly["timestamp"].dt.floor("h")
    hourly = hourly.groupby("hour", as_index=False)["bottles_filled"].sum().sort_values("hour")

    by_resin = df_mine.groupby("resin_type", as_index=False)["bottles_filled"].sum()
    by_resin = by_resin[by_resin["bottles_filled"] > 0]

    return ShiftSummaryOut(
        has_logs_today=True,
        units=units, scrap=scrap, yield_pct=round(yield_pct, 1),
        logs_submitted=int(len(df_today)), has_output_logs=True,
        hourly_timeline=[HourlyPoint(hour=row["hour"].isoformat() + "Z", units=int(row["bottles_filled"]))
                         for _, row in hourly.iterrows()],
        by_resin=[ResinPoint(resin=row["resin_type"], units=int(row["bottles_filled"]))
                 for _, row in by_resin.iterrows()],
    )
