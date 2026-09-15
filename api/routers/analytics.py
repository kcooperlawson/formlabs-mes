"""Nexus Analytics, ported from pages/Analytics_Hub.py: the rolling 7-day
intelligence dashboard - KPIs with week-over-week deltas, a live ticking
daily expectation/projection, production velocity, formulation mix,
downtime pareto, an operator contribution heatmap, and the fill-weight
give-away panel. Gated by view_analytics, matching the original.

Reuses pace.expected_for_day and fill_weight.giveaway/band_percent exactly
as the page does - both are already framework-agnostic pure functions, so
there is nothing Streamlit-shaped to port for the math itself, only the
presentation.
"""
from datetime import date, datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends

import crud
import fill_weight
import pace
from api.deps import require_ability
from api.schemas.analytics import (AnalyticsKpis, AnalyticsOverviewOut, DowntimeReason,
                                   FillWeightOut, HeatmapCell, LiveTicker, PumpDeviation,
                                   ResinOutput, TrendPoint, WeightReading)
from resin_palette import resin_color_map, stored_color_map

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/overview", response_model=AnalyticsOverviewOut)
def overview(user: dict = Depends(require_ability("view_analytics"))):
    today = date.today()
    sevendays_ago = today - timedelta(days=7)
    prev_sevendays_ago = sevendays_ago - timedelta(days=7)

    df_logs = crud.get_production_logs_df(start_date=prev_sevendays_ago, end_date=today)
    df_dt = crud.get_downtime_logs_df()
    settings = crud.get_plant_settings()

    if not df_logs.empty:
        df_logs["date_obj"] = pd.to_datetime(df_logs["date"]).dt.date
        df_logs["date_str"] = df_logs["date_obj"].astype(str)
    else:
        df_logs = pd.DataFrame(columns=["date_obj", "date_str", "log_type", "bottles_filled",
                                        "scrap_empty", "scrap_filled", "resin_type"])

    pour_df = df_logs[df_logs["log_type"] == "Hourly Bottle Count"].copy()

    if not pour_df.empty:
        users_df = crud.get_all_users_df()
        id_to_name = dict(zip(users_df["id"], users_df["full_name"])) if not users_df.empty else {}
        pour_df["display_operator"] = pour_df.apply(
            lambda r: id_to_name.get(r.get("operator_id"), r["operator_name"]), axis=1)
    else:
        pour_df["display_operator"] = pour_df.get("operator_name")

    pour_7d = pour_df[pour_df["date_obj"] >= sevendays_ago] if not pour_df.empty else pour_df
    dt_7d = df_dt[pd.to_datetime(df_dt["date"]).dt.date >= sevendays_ago] if not df_dt.empty else pd.DataFrame()

    total_poured_7d = int(pour_7d["bottles_filled"].sum()) if not pour_7d.empty else 0
    total_scrap_7d = int(pour_7d["scrap_empty"].sum() + pour_7d["scrap_filled"].sum()) if not pour_7d.empty else 0
    yield_7d = (total_poured_7d / (total_poured_7d + total_scrap_7d) * 100) if (total_poured_7d + total_scrap_7d) > 0 else 100.0
    total_dt_mins = float(dt_7d["duration_min"].sum()) if not dt_7d.empty else 0.0

    pour_prev7d = pour_df[(pour_df["date_obj"] >= prev_sevendays_ago) & (pour_df["date_obj"] < sevendays_ago)] if not pour_df.empty else pour_df
    prev_poured = int(pour_prev7d["bottles_filled"].sum()) if not pour_prev7d.empty else 0
    pour_delta_pct = ((total_poured_7d - prev_poured) / prev_poured * 100) if prev_poured > 0 else 0.0

    kpis = AnalyticsKpis(
        total_poured_7d=total_poured_7d, pour_delta_pct=round(pour_delta_pct, 1),
        yield_7d=round(yield_7d, 2), yield_target_pct=float(settings.get("yield_target_pct", 99.0)),
        total_scrap_7d=total_scrap_7d, downtime_hours_7d=round(total_dt_mins / 60, 1),
        downtime_minutes_7d=int(total_dt_mins),
    )

    # --- live ticking daily expectation/projection --------------------------
    time_now = datetime.now()
    s1_h, s1_m = map(int, settings["shift_1_start"].split(":"))
    shift_1_start = time_now.replace(hour=s1_h, minute=s1_m, second=0)
    if time_now < shift_1_start:
        elapsed_hrs = (time_now - (shift_1_start - timedelta(days=1))).total_seconds() / 3600.0
    else:
        elapsed_hrs = (time_now - shift_1_start).total_seconds() / 3600.0
    total_shift_length = float(settings["shift_1_hours"]) + float(settings["shift_2_hours"])
    elapsed_hrs = min(total_shift_length, max(0.1, elapsed_hrs))
    remaining_hrs = max(0.0, total_shift_length - elapsed_hrs)

    _pace = pace.expected_for_day(settings, now=time_now)
    live_target_lph = float(_pace["rate_lph"] or settings.get("target_lph", 400.0))
    live_today_poured = int(pour_df[pour_df["date_obj"] == today]["bottles_filled"].sum()) if not pour_df.empty else 0
    expected_right_now = _pace["expected_l"] if _pace["derived"] else live_target_lph * elapsed_hrs
    live_rate = live_today_poured / elapsed_hrs
    projected_daily = live_today_poured + ((live_rate if elapsed_hrs > 0.5 else live_target_lph) * remaining_hrs)

    live_ticker = LiveTicker(expected_now_l=round(expected_right_now, 0), projected_daily_l=round(projected_daily, 0))

    # --- production velocity stream ------------------------------------------
    velocity_trend = []
    if not pour_7d.empty:
        trend_df = pour_7d.groupby("date_str")["bottles_filled"].sum().reset_index()
        velocity_trend = [TrendPoint(date=row["date_str"], units=int(row["bottles_filled"]))
                          for _, row in trend_df.iterrows()]

    # --- formulation output donut ---------------------------------------------
    formulation_output = []
    if not pour_7d.empty:
        resin_grp = pour_7d.groupby("resin_type")["bottles_filled"].sum().reset_index()
        colours = resin_color_map(resin_grp["resin_type"].tolist(), stored_color_map(crud.get_all_resin_specs_df("ALL")))
        formulation_output = [
            ResinOutput(resin=row["resin_type"], units=int(row["bottles_filled"]),
                       color=colours.get(row["resin_type"], "#9AA3AE"))
            for _, row in resin_grp.iterrows()
        ]

    # --- downtime pareto -------------------------------------------------
    downtime_pareto = []
    if not dt_7d.empty:
        dt_grp = dt_7d.groupby("reason")["duration_min"].sum().reset_index().sort_values("duration_min", ascending=False)
        downtime_pareto = [DowntimeReason(reason=row["reason"], minutes=float(row["duration_min"]))
                          for _, row in dt_grp.iterrows()]

    # --- operator contribution heatmap (top 5 over the whole 14-day fetch) ----
    operator_matrix = []
    top_operators: list[str] = []
    if not pour_df.empty:
        op_matrix = pour_df.groupby(["display_operator", "date_str"])["bottles_filled"].sum().reset_index()
        top_ops = op_matrix.groupby("display_operator")["bottles_filled"].sum().nlargest(5).index
        top_operators = list(top_ops)
        op_matrix = op_matrix[op_matrix["display_operator"].isin(top_ops)]
        operator_matrix = [
            HeatmapCell(operator=row["display_operator"], date=row["date_str"], units=int(row["bottles_filled"]))
            for _, row in op_matrix.iterrows()
        ]

    # --- fill weight give-away -------------------------------------------
    fw = pour_df[pour_df["check_weight_g"].notna()].copy() if "check_weight_g" in pour_df.columns else pd.DataFrame()
    if fw.empty:
        fill_weight_out = FillWeightOut(has_readings=False, samples=0, in_band_pct="0%", mean_deviation=0.0,
                                        kg_above_target=0.0, scatter=[], by_pump=[], worst_pump_note=None)
    else:
        fw["weight_deviation_g"] = pd.to_numeric(fw["weight_deviation_g"], errors="coerce")
        fw = fw[fw["weight_deviation_g"].notna()]

        summary = fill_weight.giveaway(zip(fw["weight_deviation_g"], fw["bottles_filled"].fillna(0)))
        in_band = int((fw["weight_status"] == "in").sum())
        judged = int(fw["weight_status"].isin(["in", "over", "under"]).sum())

        scatter = [
            WeightReading(
                timestamp=pd.Timestamp(row["timestamp"]).isoformat(), deviation_g=float(row["weight_deviation_g"]),
                pump_station=row["pump_station"], resin_type=row.get("resin_type"),
                check_weight_g=float(row["check_weight_g"]) if pd.notna(row.get("check_weight_g")) else None,
                operator_name=row["operator_name"], status=row.get("weight_status"),
            )
            for _, row in fw.sort_values("timestamp").iterrows()
        ]

        by_pump_df = (fw.groupby("pump_station")["weight_deviation_g"].agg(["mean", "count"]).reset_index()
                     .sort_values("mean", ascending=False))
        by_pump = [PumpDeviation(pump_station=row["pump_station"], mean_deviation=round(float(row["mean"]), 2),
                                 count=int(row["count"]))
                  for _, row in by_pump_df.iterrows()]

        worst_note = None
        if by_pump:
            worst = by_pump[0]
            if worst.mean_deviation > 0.5:
                worst_note = (f"{worst.pump_station} is averaging {worst.mean_deviation:+.1f} g against target "
                             f"across {worst.count} readings. Every gram above target is resin out of the door "
                             f"on every cartridge that pump fills.")

        fill_weight_out = FillWeightOut(
            has_readings=True, samples=summary["samples"],
            in_band_pct=fill_weight.band_percent(in_band, judged),
            mean_deviation=summary["mean_deviation"], kg_above_target=summary["kg"],
            scatter=scatter, by_pump=by_pump, worst_pump_note=worst_note,
        )

    return AnalyticsOverviewOut(
        kpis=kpis, live_ticker=live_ticker, velocity_trend=velocity_trend,
        formulation_output=formulation_output, downtime_pareto=downtime_pareto,
        operator_matrix=operator_matrix, top_operators=top_operators, fill_weight=fill_weight_out,
    )
