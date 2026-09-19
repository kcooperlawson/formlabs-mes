"""Live SCADA - the manager/admin plant dashboard, ported from Home.py's
post-login body (everything before the login form, and the login form
itself, stay Streamlit-only: this API assumes the React app's own
AuthProvider already handled sign-in). One endpoint computes everything the
page needs for a given filter selection, mirroring Home.py's own
filter-then-aggregate flow exactly - down to reusing crud.log_litres,
shift_clock.compute_shift_status, pace.expected_for_shift and
record_health.record_state directly rather than re-deriving any of that
arithmetic.

Gated by the view_scada ability (crud.can_view_scada / the "view_scada"
ability), not a bare role check - granted to manager/admin by default but
grantable to anyone via Extra Abilities, same door Home.py itself uses
(`can("view_scada")`).

Home.py also loads get_downtime_logs_df() and get_assigned_runs_df() into
df_dt/df_runs, but never reads either again afterward - dead fetches in the
original. Not reproduced here.
"""
from datetime import date as date_cls, datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException

import crud
import pace
from record_health import record_state
from shift_clock import compute_shift_status
from api.deps import require_ability
from api.schemas.scada import (
    CartTypeCount, HealthOut, LeaderboardEntry, LogRow, PackedByResinLot,
    PackingOut, PouringOut, ScadaFilters, ScadaOverviewOut, TrajectoryOut,
)

router = APIRouter(prefix="/scada", tags=["scada"])

HORIZONS = ("live", "specific", "week", "month", "all")
SORTS = ("newest", "oldest", "units", "resin")


@router.get("/overview", response_model=ScadaOverviewOut)
def overview(
    horizon: str = "live",
    date: str | None = None,
    pump: str = "All Pumps",
    resin: str = "All Resins",
    operator: str = "All Operators",
    shift: str = "All Shifts",
    sort: str = "newest",
    user: dict = Depends(require_ability("view_scada")),
):
    if horizon not in HORIZONS:
        raise HTTPException(status_code=400, detail=f"horizon must be one of {HORIZONS}")
    if sort not in SORTS:
        raise HTTPException(status_code=400, detail=f"sort must be one of {SORTS}")

    df_logs = crud.get_production_logs_df()
    specs_df = crud.get_all_resin_specs_df("ALL")
    settings = crud.get_plant_settings()

    spec_dict = {}
    if not specs_df.empty:
        for _, r in specs_df.iterrows():
            key = f"{str(r['cartridge_type']).strip().lower()}_{str(r['resin_name']).strip().lower()}"
            spec_dict[key] = float(r["actual_spec_g"])

    if not df_logs.empty:
        df_logs["date_obj"] = pd.to_datetime(df_logs["date"]).dt.date
        df_logs["date_str"] = df_logs["date_obj"].astype(str)
        all_dates = sorted(df_logs["date_str"].unique().tolist(), reverse=True)
    else:
        all_dates = []

    filters = ScadaFilters(
        pumps=sorted(df_logs["pump_station"].dropna().unique().tolist()) if not df_logs.empty else [],
        resins=sorted(df_logs["resin_type"].dropna().unique().tolist()) if not df_logs.empty else [],
        operators=sorted(df_logs["operator_name"].dropna().unique().tolist()) if not df_logs.empty else [],
        shifts=sorted(df_logs["shift"].dropna().unique().tolist()) if not df_logs.empty else [],
        dates=all_dates,
    )

    # --- health: is the record still being fed? ---------------------------
    shift_status = compute_shift_status(settings)
    is_shift_active = shift_status["is_active"]
    health_raw = record_state(crud.last_log_at(), is_shift_active,
                              shift_started_at=shift_status.get("started_at"))
    health = HealthOut(state=health_raw["state"], is_alarm=health_raw["is_alarm"],
                       is_warning=health_raw["is_warning"], message=health_raw["message"])

    # --- filtering, mirroring Home.py's time-horizon + dropdown filters ----
    filtered_df = df_logs.copy() if not df_logs.empty else pd.DataFrame()
    today_d = date_cls.today()

    if not filtered_df.empty:
        if horizon == "live":
            if is_shift_active:
                filtered_df = filtered_df[
                    (filtered_df["date_obj"] == today_d) & (filtered_df["shift"] == shift_status["shift_name"])]
            else:
                filtered_df = filtered_df.iloc[0:0]
        elif horizon == "specific":
            target_date = date or (all_dates[0] if all_dates else str(today_d))
            filtered_df = filtered_df[filtered_df["date_str"] == target_date]
        elif horizon == "week":
            filtered_df = filtered_df[filtered_df["date_obj"] >= (today_d - timedelta(days=7))]
        elif horizon == "month":
            filtered_df = filtered_df[filtered_df["date_obj"] >= (today_d - timedelta(days=30))]

        if pump != "All Pumps":
            filtered_df = filtered_df[filtered_df["pump_station"] == pump]
        if resin != "All Resins":
            filtered_df = filtered_df[filtered_df["resin_type"] == resin]
        if operator != "All Operators":
            filtered_df = filtered_df[filtered_df["operator_name"] == operator]
        if shift != "All Shifts":
            filtered_df = filtered_df[filtered_df["shift"] == shift]

    pour_df = filtered_df[filtered_df["log_type"] == "Hourly Bottle Count"] if not filtered_df.empty else pd.DataFrame()
    pack_df = filtered_df[filtered_df["log_type"] == "Packing Count"] if not filtered_df.empty else pd.DataFrame()

    # --- pouring math -------------------------------------------------
    total_poured = int(pour_df["bottles_filled"].sum()) if not pour_df.empty else 0
    total_scrap = int(pour_df["scrap_empty"].sum() + pour_df["scrap_filled"].sum()) if not pour_df.empty else 0
    liters_output = 0.0
    resin_mass_kg = 0.0
    cart_type_counts: dict[str, int] = {}
    if not pour_df.empty:
        for _, r in pour_df.iterrows():
            b_count = float(r.get("bottles_filled", 0) or 0)
            c_type = str(r.get("cartridge_type", "V2")).strip() or "V2"
            r_name = str(r.get("resin_type", "")).strip()
            cart_type_counts[c_type] = cart_type_counts.get(c_type, 0) + int(b_count)
            liters_output += crud.log_litres(b_count, c_type, r.get("litres_poured"))
            unit_g = spec_dict.get(f"{c_type.lower()}_{r_name.lower()}", 5500.0 if "RPS" in c_type.upper() else 1110.0)
            resin_mass_kg += b_count * (unit_g / 1000.0)

    # --- packing math -------------------------------------------------
    total_packed = int(pack_df["bottles_filled"].sum()) if not pack_df.empty else 0
    unpacked_wip = total_poured - total_packed
    total_skids_est = 0.0
    if not pack_df.empty:
        for _, r in pack_df.iterrows():
            b_count = float(r.get("bottles_filled", 0) or 0)
            skid_size = 500.0
            if not specs_df.empty:
                match = specs_df[specs_df["resin_name"] == r["resin_type"]]
                if not match.empty:
                    skid_size = float(match.iloc[0].get("units_per_skid", 500))
            if skid_size > 0:
                total_skids_est += b_count / skid_size

    # --- shift/pace ---------------------------------------------------
    target_rate_lh = float(settings.get("target_lph", 400.0))
    elapsed_net = shift_status["elapsed_net"]
    active_shift_net = shift_status["shift_net_hours"]
    operating_hours = elapsed_net if (horizon == "live" and is_shift_active) else active_shift_net
    run_velocity_lh = (liters_output / operating_hours) if operating_hours > 0 else 0.0
    pack_velocity_uh = (total_packed / operating_hours) if operating_hours > 0 else 0.0

    pace_info = pace.expected_for_shift(settings, shift_status["shift_name"], shift_status.get("started_at")) \
        if is_shift_active else {"expected_l": 0.0, "rate_lph": target_rate_lh, "shift_target_l": 0.0,
                                 "stations": [], "derived": False}
    target_rate_lh = float(pace_info["rate_lph"] or target_rate_lh)
    oee_pct = (run_velocity_lh / target_rate_lh) * 100.0 if target_rate_lh > 0 else 0.0
    yield_pct = (total_poured / (total_poured + total_scrap) * 100.0) if (total_poured + total_scrap) > 0 else 100.0

    live_and_active = is_shift_active and horizon == "live"
    if live_and_active:
        expected_now = pace_info["expected_l"] if pace_info["derived"] else target_rate_lh * max(0.1, operating_hours)
        pace_variance_l = liters_output - expected_now
        expected_display = f"{expected_now:,.0f} L"
        status_badge = f"{shift_status['shift_name']} Active"
    else:
        pace_variance_l = 0.0
        expected_display = "—"
        status_badge = "Floor Idle"

    remaining_hours = shift_status["remaining_hours"]
    blended_rate = run_velocity_lh if operating_hours > 0.5 else target_rate_lh
    projected_total = liters_output + (blended_rate * remaining_hours)

    trajectory = None
    if horizon == "live":
        trajectory = TrajectoryOut(
            is_live=is_shift_active, active_shift_name=shift_status["shift_name"],
            elapsed_net=elapsed_net, remaining_hours=remaining_hours, shift_pct=shift_status["shift_pct"],
            expected_display=expected_display, projected_total=projected_total,
            pace_variance_l=pace_variance_l, oee_pct=oee_pct, status_badge=status_badge,
            next_shift_label=shift_status.get("next_shift_label") or "",
        )

    leaderboard = []
    if not pour_df.empty:
        op_stats = []
        for op in pour_df["operator_name"].unique():
            op_data = pour_df[pour_df["operator_name"] == op]
            op_liters = sum(crud.log_litres(float(r.get("bottles_filled", 0) or 0),
                                            str(r.get("cartridge_type", "V2")), r.get("litres_poured"))
                            for _, r in op_data.iterrows())
            timestamps = pd.to_datetime(op_data["timestamp"])
            time_span_hours = (timestamps.max() - timestamps.min()).total_seconds() / 3600.0
            op_hours = min(operating_hours, max(1.0, time_span_hours + 1.0))
            op_stats.append((op, op_liters / op_hours if op_hours > 0 else 0.0))
        op_stats.sort(key=lambda x: x[1], reverse=True)
        leaderboard = [LeaderboardEntry(operator=op, velocity_lh=vel) for op, vel in op_stats[:3]]

    by_resin_lot = []
    if not pack_df.empty:
        grp = pack_df.groupby(["resin_type", "lot_number"])["bottles_filled"].sum().reset_index()
        for _, row in grp.iterrows():
            skid_size = 500.0
            if not specs_df.empty:
                match = specs_df[specs_df["resin_name"] == row["resin_type"]]
                if not match.empty:
                    skid_size = float(match.iloc[0].get("units_per_skid", 500))
            skids = row["bottles_filled"] / skid_size if skid_size > 0 else 0.0
            by_resin_lot.append(PackedByResinLot(resin=row["resin_type"], lot_number=row["lot_number"],
                                                 units=int(row["bottles_filled"]), skids=skids))

    # --- role-based view toggle (packers never actually reach this endpoint
    # in the normal flow - the React router sends them to the Operator Form -
    # but the branching is kept for parity with anyone granted view_scada
    # some other way) ----------------------------------------------------
    role = user["role"]
    show_pouring = role != "packer"
    show_packing = bool(settings.get("enable_packing", True)) and role in ("manager", "admin", "packer")

    # --- log stream ------------------------------------------------
    stream_df = filtered_df
    if role == "operator":
        stream_title = "Filtered Pouring Log Stream"
        stream_df = stream_df[stream_df["log_type"] == "Hourly Bottle Count"] if not stream_df.empty else stream_df
    elif role == "packer":
        stream_title = "Filtered Packing Log Stream"
        stream_df = stream_df[stream_df["log_type"] == "Packing Count"] if not stream_df.empty else stream_df
    else:
        stream_title = "Filtered Master Production Stream"

    log_stream = []
    if not stream_df.empty:
        sorted_df = stream_df.copy()
        if sort == "newest":
            sorted_df = sorted_df.sort_values(by="timestamp", ascending=False)
        elif sort == "oldest":
            sorted_df = sorted_df.sort_values(by="timestamp", ascending=True)
        elif sort == "units":
            sorted_df = sorted_df.sort_values(by="bottles_filled", ascending=False)
        elif sort == "resin":
            sorted_df = sorted_df.sort_values(by="resin_type", ascending=True)

        for _, r in sorted_df.iterrows():
            ts = pd.to_datetime(r["timestamp"])
            if ts.tzinfo is None:
                ts = ts.tz_localize("UTC")
            log_stream.append(LogRow(
                timestamp=ts.isoformat(), date=str(r["date_str"]), log_type=r["log_type"],
                operator_name=r["operator_name"], pump_station=r["pump_station"],
                cartridge_type=r["cartridge_type"], resin_type=r["resin_type"],
                lot_number=str(r.get("lot_number")) if pd.notna(r.get("lot_number")) else "",
                bottles_filled=int(r["bottles_filled"] or 0), scrap_empty=int(r["scrap_empty"] or 0),
                scrap_filled=int(r["scrap_filled"] or 0), notes=str(r.get("notes") or ""),
            ))

    return ScadaOverviewOut(
        health=health,
        headline_liters=liters_output,
        headline_pace_variance_l=pace_variance_l,
        headline_is_live=live_and_active,
        filters=filters,
        show_pouring=show_pouring,
        show_packing=show_packing,
        pouring=PouringOut(
            liters_output=liters_output, resin_mass_kg=resin_mass_kg, run_velocity_lh=run_velocity_lh,
            target_rate_lh=target_rate_lh, yield_pct=yield_pct, total_scrap=total_scrap,
            cart_type_counts=[CartTypeCount(cartridge_type=t, units=n)
                             for t, n in sorted(cart_type_counts.items(), key=lambda kv: -kv[1])],
            trajectory=trajectory, leaderboard=leaderboard,
        ) if show_pouring else None,
        packing=PackingOut(
            total_packed=total_packed, total_skids_est=total_skids_est, pack_velocity_uh=pack_velocity_uh,
            unpacked_wip=unpacked_wip, by_resin_lot=by_resin_lot,
        ) if show_packing else None,
        log_stream=log_stream,
        log_stream_title=stream_title,
    )
