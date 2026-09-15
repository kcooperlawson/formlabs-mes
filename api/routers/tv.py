"""Plant Command wall display, ported from pages/Tv_Dashboard.py - the big-
number board a TV on the floor shows: today's pace against target, the top
pourers, the packing breakdown, and active work orders.

Two independent notions of "the current shift" exist here on purpose, exactly
as the original page has them: `active_shift` (naive datetime.now(), no
operating-days awareness - simple wall-clock math against the shift start
times) drives every KPI card, while shift_clock.compute_shift_status (the
operating-days-aware version used everywhere else) feeds ONLY the stalled-
record health alarm. Collapsing them into one would be a real behavior change,
not a cleanup - ported byte-for-byte for fidelity, same as Analytics Hub's
live ticker.

The 10-second auto-refresh becomes a plain refetchInterval on the frontend;
the "screen sweep" arrival animation and the one-shot "build complete" finale
are pure client-side presentation state (session-lifetime, like the
st.session_state flags they replace) and have no server component here.
"""
from datetime import date, datetime, timedelta

import pandas as pd
from fastapi import APIRouter, Depends

import crud
import pace
from api.deps import require_role
from api.schemas.tv import (PackingBreakdownRow, TopPourer, TvHealth, TvOverviewOut,
                            WorkOrderRow)
from record_health import record_state
from resin_palette import resin_color_map, stored_color_map
from shift_clock import compute_shift_status

router = APIRouter(prefix="/tv", tags=["tv"])


@router.get("/overview", response_model=TvOverviewOut)
def overview(mode: str = "auto", user: dict = Depends(require_role("manager", "admin"))):
    settings = crud.get_plant_settings()
    packing_enabled = bool(settings.get("enable_packing", True))
    show_runs_card = not bool(settings.get("simple_mode", True))

    df_logs = crud.get_production_logs_df()
    today_str = date.today().strftime("%Y-%m-%d")
    if not df_logs.empty:
        df_logs = df_logs.copy()
        df_logs["date_str"] = pd.to_datetime(df_logs["date"]).dt.strftime("%Y-%m-%d")
        df_today = df_logs[df_logs["date_str"] == today_str]
    else:
        df_today = pd.DataFrame()

    df_today_pour = df_today[df_today["log_type"] == "Hourly Bottle Count"] if not df_today.empty else pd.DataFrame()
    df_today_pack = df_today[df_today["log_type"] == "Packing Count"] if not df_today.empty else pd.DataFrame()

    if not df_today_pour.empty:
        users_df = crud.get_all_users_df()
        id_to_name = dict(zip(users_df["id"], users_df["full_name"])) if not users_df.empty else {}
        df_today_pour = df_today_pour.copy()
        df_today_pour["display_operator"] = df_today_pour.apply(
            lambda r: id_to_name.get(r.get("operator_id"), r["operator_name"]), axis=1)

    def calculate_liters(df_subset):
        total_l = 0.0
        for _, r in df_subset.iterrows():
            b_count = float(r.get("bottles_filled", 0) or 0)
            c_type = str(r.get("cartridge_type", "V2")).upper()
            total_l += crud.log_litres(b_count, c_type, r.get("litres_poured"))
        return total_l

    df_s1 = df_today_pour[df_today_pour["shift"] == "Shift 1"] if not df_today_pour.empty else pd.DataFrame()
    df_s2 = df_today_pour[df_today_pour["shift"] == "Shift 2"] if not df_today_pour.empty else pd.DataFrame()
    s1_liters = calculate_liters(df_s1)
    s2_liters = calculate_liters(df_s2)
    total_liters_today = calculate_liters(df_today_pour)

    total_poured = int(df_today_pour["bottles_filled"].sum()) if not df_today_pour.empty else 0
    total_packed = int(df_today_pack["bottles_filled"].sum()) if not df_today_pack.empty else 0

    time_now = datetime.now()
    s1_h, s1_m = map(int, settings["shift_1_start"].split(":"))
    s2_h, s2_m = map(int, settings["shift_2_start"].split(":"))
    shift_1_start = time_now.replace(hour=s1_h, minute=s1_m, second=0)
    shift_2_start = time_now.replace(hour=s2_h, minute=s2_m, second=0)

    if mode != "daily":
        if time_now < shift_1_start:
            shift_2_start = shift_2_start - timedelta(days=1)
            active_shift = "Shift 2"
            shift_start = shift_2_start
            shift_length_hrs = float(settings["shift_2_hours"])
            current_output = s2_liters
        elif shift_1_start <= time_now < shift_2_start:
            active_shift = "Shift 1"
            shift_start = shift_1_start
            shift_length_hrs = float(settings["shift_1_hours"])
            current_output = s1_liters
        else:
            active_shift = "Shift 2"
            shift_start = shift_2_start
            shift_length_hrs = float(settings["shift_2_hours"])
            current_output = s2_liters
        elapsed_hours = min(shift_length_hrs, max(0.25, (time_now - shift_start).total_seconds() / 3600.0))
    else:
        active_shift = "ALL SHIFTS (DAILY TOTAL)"
        current_output = total_liters_today
        total_shift_length = float(settings["shift_1_hours"]) + float(settings["shift_2_hours"])
        if time_now < shift_1_start:
            total_elapsed = (time_now - (shift_1_start - timedelta(days=1))).total_seconds() / 3600.0
        else:
            total_elapsed = (time_now - shift_1_start).total_seconds() / 3600.0
        elapsed_hours = min(total_shift_length, max(0.25, total_elapsed))

    current_run_rate = current_output / elapsed_hours

    if active_shift == "Shift 1":
        df_scope_pour = df_s1
        df_scope_pack = df_today_pack[df_today_pack["shift"] == "Shift 1"] if not df_today_pack.empty else df_today_pack
    elif active_shift == "Shift 2":
        df_scope_pour = df_s2
        df_scope_pack = df_today_pack[df_today_pack["shift"] == "Shift 2"] if not df_today_pack.empty else df_today_pack
    else:
        df_scope_pour = df_today_pour
        df_scope_pack = df_today_pack

    scope_packed = int(df_scope_pack["bottles_filled"].sum()) if not df_scope_pack.empty else 0

    if active_shift == "ALL SHIFTS (DAILY TOTAL)":
        remaining_hrs = max(0.0, total_shift_length - elapsed_hours)
        _pace = pace.expected_for_day(settings, now=time_now)
    else:
        remaining_hrs = max(0.0, shift_length_hrs - elapsed_hours)
        _pace = pace.expected_for_shift(settings, active_shift, shift_start, now=time_now)

    expected_now = _pace["expected_l"]
    target_lph = _pace["rate_lph"]
    blended_rate = current_run_rate if elapsed_hours > 0.5 else target_lph
    projected_total = current_output + (blended_rate * remaining_hrs)
    shift_target_l = max(0.0, _pace["shift_target_l"])
    build_pct = (current_output / shift_target_l * 100.0) if shift_target_l > 0 else 0.0

    _shift = compute_shift_status(settings)
    _health = record_state(crud.last_log_at(), _shift["is_active"], shift_started_at=_shift.get("started_at"))
    health = TvHealth(state=_health["state"], is_alarm=_health["is_alarm"],
                      is_warning=_health["is_warning"], message=_health["message"])

    top_pourers: list[TopPourer] = []
    if not df_scope_pour.empty:
        op_stats = []
        for op in df_scope_pour["display_operator"].unique():
            op_data = df_scope_pour[df_scope_pour["display_operator"] == op]
            op_liters = 0.0
            for _, r in op_data.iterrows():
                b_count = float(r.get("bottles_filled", 0) or 0)
                c_type = str(r.get("cartridge_type", "V2")).upper()
                op_liters += crud.log_litres(b_count, c_type, r.get("litres_poured"))
            timestamps = pd.to_datetime(op_data["timestamp"])
            time_span_hours = (timestamps.max() - timestamps.min()).total_seconds() / 3600.0
            op_hours = min(elapsed_hours, max(1.0, time_span_hours + 1.0))
            vel = op_liters / op_hours if op_hours > 0 else 0
            op_stats.append((op, vel))
        op_stats.sort(key=lambda x: x[1], reverse=True)
        top_pourers = [TopPourer(operator=op, rate_lph=round(vel, 1)) for op, vel in op_stats[:5]]

    packing_breakdown: list[PackingBreakdownRow] = []
    if packing_enabled and not df_scope_pack.empty:
        specs_df = crud.get_all_resin_specs_df("ALL")
        pack_colours = stored_color_map(specs_df)
        pack_grp = df_scope_pack.groupby(["resin_type", "lot_number"])["bottles_filled"].sum().reset_index()
        for _, row in pack_grp.iterrows():
            res, lot, qty = row["resin_type"], row["lot_number"], int(row["bottles_filled"])
            skid_size = 500.0
            if not specs_df.empty:
                match = specs_df[specs_df["resin_name"] == res]
                if not match.empty:
                    skid_size = float(match.iloc[0].get("units_per_skid", 500))
            colours = resin_color_map([res], pack_colours)
            packing_breakdown.append(PackingBreakdownRow(
                resin=res, lot_number=lot, units=qty, color=colours.get(res, "#9AA3AE"),
                skids=round(qty / skid_size, 1) if skid_size > 0 else 0.0,
            ))

    work_orders: list[WorkOrderRow] = []
    if show_runs_card:
        df_runs = crud.get_assigned_runs_df()
        if not df_runs.empty:
            run_colours = stored_color_map(crud.get_all_resin_specs_df("ALL"))
            active_runs = df_runs[df_runs["status"].isin(["Active", "Pouring"])]
            for _, run in active_runs.iterrows():
                target = int(run["target_units"])
                current = int(run["current_units"])
                prog = min(1.0, current / target) if target > 0 else 0.0
                colours = resin_color_map([run["resin_type"]], run_colours)
                work_orders.append(WorkOrderRow(
                    resin_type=run["resin_type"], color=colours.get(run["resin_type"], "#9AA3AE"),
                    pump_station=run["pump_station"], current_units=current, target_units=target,
                    progress_pct=round(prog * 100.0, 1),
                ))

    return TvOverviewOut(
        active_shift=active_shift, health=health,
        current_output_l=round(current_output, 1), current_run_rate_lph=round(current_run_rate, 1),
        expected_now_l=round(expected_now, 1), target_lph=round(target_lph, 1),
        pace_derived=bool(_pace["derived"]), pace_station_count=len(_pace["stations"]),
        pace_gap_l=round(current_output - expected_now, 1),
        projected_total_l=round(projected_total, 1), shift_target_l=round(shift_target_l, 1),
        build_pct=round(build_pct, 2), scope_packed=scope_packed,
        total_poured=total_poured, total_packed=total_packed, unpacked_wip=total_poured - total_packed,
        packing_enabled=packing_enabled, show_runs_card=show_runs_card,
        top_pourers=top_pourers, packing_breakdown=packing_breakdown, work_orders=work_orders,
    )
