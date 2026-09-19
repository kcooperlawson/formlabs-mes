"""My Shift Summary - a read-only, on-demand personal breakdown, ported
from pages/operator_form/summary_tab.py. Always scoped to the signed-in
operator/packer's own logs (the original has no plant-wide variant at all -
that's Manager Cockpit's job, behind view_manager_cockpit, a later phase).

Nothing here is written anywhere; it's aggregated fresh from today's
already-submitted logs on every call, same as the original's own comment
says of itself.
"""
from datetime import date

import pandas as pd
from fastapi import APIRouter, Depends

import crud
from api.deps import get_current_user, resolve_operator_name
from api.schemas.summary import CartridgePoint, HourlyPoint, MonthlyRecapOut, ResinPoint, ShiftSummaryOut

router = APIRouter(prefix="/summary", tags=["summary"])


def _ordinal(n: int) -> str:
    if 10 <= n % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


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
        return ShiftSummaryOut(has_logs_today=True, units=0, litres=0.0, scrap=0, yield_pct=100.0,
                               logs_submitted=int(len(df_today)), has_output_logs=False)

    # crud.log_litres is the one place bottles-filled-plus-format becomes a
    # volume anywhere in the app (tank levels, exports, the wall display) - a
    # measured litres_poured wins outright when a row has one, same as
    # everywhere else, so a bulk pour reads the same here as it does there.
    df_mine = df_mine.copy()
    df_mine["litres"] = df_mine.apply(
        lambda row: crud.log_litres(row["bottles_filled"], row["cartridge_type"], row["litres_poured"]), axis=1)
    litres_total = float(df_mine["litres"].sum())

    hourly = df_mine.copy()
    hourly["hour"] = hourly["timestamp"].dt.floor("h")
    hourly = hourly.groupby("hour", as_index=False)["bottles_filled"].sum().sort_values("hour")

    by_resin = df_mine.groupby("resin_type", as_index=False).agg(
        bottles_filled=("bottles_filled", "sum"), litres=("litres", "sum"))
    by_resin = by_resin[by_resin["bottles_filled"] > 0]

    by_cartridge = df_mine.groupby("cartridge_type", as_index=False).agg(
        bottles_filled=("bottles_filled", "sum"), litres=("litres", "sum"))
    by_cartridge = by_cartridge[by_cartridge["bottles_filled"] > 0]

    return ShiftSummaryOut(
        has_logs_today=True,
        units=units, litres=round(litres_total, 1), scrap=scrap, yield_pct=round(yield_pct, 1),
        logs_submitted=int(len(df_today)), has_output_logs=True,
        hourly_timeline=[HourlyPoint(hour=row["hour"].isoformat() + "Z", units=int(row["bottles_filled"]))
                         for _, row in hourly.iterrows()],
        by_resin=[ResinPoint(resin=row["resin_type"], units=int(row["bottles_filled"]), litres=round(row["litres"], 1))
                 for _, row in by_resin.iterrows()],
        by_cartridge=[CartridgePoint(cartridge_type=row["cartridge_type"], units=int(row["bottles_filled"]),
                                     litres=round(row["litres"], 1))
                     for _, row in by_cartridge.iterrows()],
    )


# The one-time "wrapped"-style card shown after a fresh sign-in - see
# LoginRecap.tsx. Always the signed-in user's own logs: unlike /today, a
# manager's "Impersonate Operator" pick in Debug Mode has no bearing on
# what THEY personally poured this month, so this ignores as_operator
# entirely and filters by the caller's own operator_id.
@router.get("/monthly", response_model=MonthlyRecapOut)
def monthly(user: dict = Depends(get_current_user)):
    today_d = date.today()
    start_of_month = today_d.replace(day=1)
    month_label = today_d.strftime("%B")

    df = crud.get_production_logs_df(start_date=start_of_month, end_date=today_d, operator_id=user["id"])
    log_type_wanted = "Packing Count" if user["role"] == "packer" else "Hourly Bottle Count"
    df_mine = df[df["log_type"] == log_type_wanted] if not df.empty else df

    if df_mine.empty:
        return MonthlyRecapOut(has_data=False, month_label=month_label, units=0)

    units = int(df_mine["bottles_filled"].sum())
    df_mine = df_mine.copy()
    df_mine["day"] = pd.to_datetime(df_mine["date"]).dt.date
    by_day = df_mine.groupby("day", as_index=False)["bottles_filled"].sum()
    best = by_day.loc[by_day["bottles_filled"].idxmax()]

    days_elapsed = (today_d - start_of_month).days + 2
    mismatches_df = crud.get_lot_verifications_df(days=days_elapsed, result="mismatch")
    mismatches = 0
    if not mismatches_df.empty:
        mismatches_df = mismatches_df.copy()
        mismatches_df["day"] = pd.to_datetime(mismatches_df["date"]).dt.date
        mismatches = int((
            (mismatches_df["operator_id"] == user["id"]) &
            (mismatches_df["day"] >= start_of_month)
        ).sum())

    return MonthlyRecapOut(
        has_data=True, month_label=month_label, units=units,
        best_day_ordinal=_ordinal(best["day"].day), best_day_units=int(best["bottles_filled"]),
        mismatches=mismatches,
    )
