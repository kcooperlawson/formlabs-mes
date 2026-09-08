
import sys
import os
from datetime import datetime, date, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from resin_palette import resin_dot, stored_color_map
from database import (
    get_production_logs_df, get_downtime_logs_df,
    delete_production_log, delete_downtime_log,
    get_all_resin_specs_df,
    do_logout,
)

st.set_page_config(page_title="Log Management | Formlabs MES", page_icon="🗑️", layout="wide")


try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Default Dark"), THEMES["Default Dark"]), unsafe_allow_html=True)

# Restore the session before deciding whether to refuse it. Without this the
# role check below runs against an empty session on any cold load - a refresh,
# a bookmark, a link opened in a new tab - and answers Access Denied to a
# manager who has every right to be here. It only ever appeared to work
# because arriving from another page carried the session in memory, and the
# one thing nobody does while testing is press F5.
import extra_streamlit_components as _stx
from database import check_authentication as _check_auth
_check_auth(_stx.CookieManager(key="auth_log_management"))

if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") not in ["manager", "admin"]:
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
from ui_shell import render_shell
from components import empty_state
cookie_manager = render_shell(show_settings=False)
current_role = st.session_state.get("user_role", "operator")

# ===================== HEADER =====================
st.markdown("## 🗑️ Log Management & Data Cleanup")
st.warning(
    "⚠️ Deletions here are **permanent** and cannot be undone. Deleting a "
    "production log automatically re-syncs the progress of whatever Work "
    "Order it was counted against, so totals stay accurate after cleanup."
)

log_tab, dt_tab = st.tabs(["💧 Production Logs (Pouring / Packing)", "⛔ Downtime Logs"])


def _confirm_bulk_delete(key_prefix: str, match_count: int):
    """Shared 'type DELETE to confirm' guard for bulk-delete-by-filter.
    Returns True exactly once, on the click that should actually fire."""
    st.text_input(
        f"Type DELETE to enable bulk delete of these {match_count} record(s)",
        key=f"{key_prefix}_confirm_text",
        placeholder="DELETE",
    )
    armed = st.session_state.get(f"{key_prefix}_confirm_text", "").strip() == "DELETE"
    return st.button(
        f"☢️ Permanently Delete All {match_count} Matching Record(s)",
        type="primary", use_container_width=True,
        disabled=not armed, key=f"{key_prefix}_bulk_btn",
    )


# ===================== 💧 PRODUCTION LOGS =====================
with log_tab:
    all_logs = get_production_logs_df()
    _resin_colours = stored_color_map(get_all_resin_specs_df("ALL"))

    if all_logs.empty:
        empty_state(
            "No production logs yet",
            "This page is for finding and removing bad or test entries. Nothing has "
            "been logged, so there is nothing to clean up.",
            icon="\U0001F5D1\uFE0F")
    else:
        all_logs["date_obj"] = pd.to_datetime(all_logs["date"]).dt.date
        # Same UTC -> plant-local conversion used everywhere else on the
        # production-log stream (Home.py, Mgr_Assigned_Runs.py) — the raw
        # column comes back tz-naive UTC from the DB.
        all_logs["timestamp_disp"] = pd.to_datetime(all_logs["timestamp"]).dt.tz_localize(
            "UTC"
        ).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d %H:%M:%S")

        min_d, max_d = all_logs["date_obj"].min(), all_logs["date_obj"].max()

        f1, f2, f3, f4, f5 = st.columns([1.2, 1.2, 1, 1, 1])
        with f1:
            start_d = st.date_input("From Date", value=min_d, min_value=min_d, max_value=max_d, key="plog_start")
        with f2:
            end_d = st.date_input("To Date", value=max_d, min_value=min_d, max_value=max_d, key="plog_end")
        with f3:
            type_opts = ["All Types"] + sorted(all_logs["log_type"].dropna().unique().tolist())
            f_type = st.selectbox("Log Type", type_opts, key="plog_type")
        with f4:
            pump_opts = ["All Pumps"] + sorted(all_logs["pump_station"].dropna().unique().tolist())
            f_pump = st.selectbox("Pump Station", pump_opts, key="plog_pump")
        with f5:
            op_opts = ["All Operators"] + sorted(all_logs["operator_name"].dropna().unique().tolist())
            f_op = st.selectbox("Operator", op_opts, key="plog_op")

        matches = all_logs[(all_logs["date_obj"] >= start_d) & (all_logs["date_obj"] <= end_d)]
        if f_type != "All Types":
            matches = matches[matches["log_type"] == f_type]
        if f_pump != "All Pumps":
            matches = matches[matches["pump_station"] == f_pump]
        if f_op != "All Operators":
            matches = matches[matches["operator_name"] == f_op]
        matches = matches.sort_values(by="timestamp", ascending=False)

        st.caption(f"**{len(matches)}** record(s) match the current filters.")
        st.markdown("---")

        if matches.empty:
            st.info("No records match the current filters.")
        else:
            show_n = st.number_input(
                "Rows to display (narrow filters or increase this to see more)",
                min_value=10, max_value=1000, value=max(10, min(100, len(matches))), step=10, key="plog_show_n",
            )
            visible = matches.head(int(show_n))

            hdr = st.columns([1.6, 1.3, 1.1, 1.2, 1.3, 1.1, 0.7])
            for c, label in zip(hdr, ["Timestamp", "Type", "Station", "Resin", "Operator", "Qty", ""]):
                c.markdown(f"**{label}**")

            for _, row in visible.iterrows():
                rc = st.columns([1.6, 1.3, 1.1, 1.2, 1.3, 1.1, 0.7])
                rc[0].caption(str(row.get("timestamp_disp", row.get("timestamp", ""))))
                rc[1].caption(str(row.get("log_type", "")))
                rc[2].caption(str(row.get("pump_station", "")))
                # A dot rather than a full pill: this grid is dense and a
                # pill per row would push the delete button off the edge.
                rc[3].markdown(
                    f"<span style='font-size:0.85rem;opacity:0.85;'>"
                    f"{resin_dot(row.get('resin_type', ''), _resin_colours.get(str(row.get('resin_type', ''))))}"
                    f"</span>", unsafe_allow_html=True)
                rc[4].caption(str(row.get("operator_name", "")))
                rc[5].caption(f"{int(row.get('bottles_filled', 0) or 0):,}")
                if rc[6].button("🗑️", key=f"del_plog_{row['id']}", help=f"Delete log #{row['id']}"):
                    delete_production_log(int(row["id"]))
                    st.toast(f"✅ Deleted production log #{int(row['id'])}")
                    st.rerun()

            if len(matches) > len(visible):
                st.caption(f"Showing {len(visible)} of {len(matches)} — increase 'Rows to display' above to see more.")

            st.markdown("---")
            with st.expander("☢️ Bulk Delete — every record matching the filters above"):
                st.caption(
                    f"This will permanently delete all **{len(matches)}** production log record(s) currently "
                    "matched by the filters above, not just the ones visible on screen."
                )
                if _confirm_bulk_delete("plog_bulk", len(matches)):
                    deleted = 0
                    for log_id in matches["id"].tolist():
                        if delete_production_log(int(log_id)):
                            deleted += 1
                    st.success(f"✅ Deleted {deleted} production log record(s).")
                    st.session_state.pop("plog_bulk_confirm_text", None)
                    st.rerun()

# ===================== ⛔ DOWNTIME LOGS =====================
with dt_tab:
    all_dt = get_downtime_logs_df()

    if all_dt.empty:
        st.info("No downtime logs exist yet.")
    else:
        all_dt["date_obj"] = pd.to_datetime(all_dt["date"]).dt.date
        all_dt["timestamp_disp"] = pd.to_datetime(all_dt["timestamp"]).dt.tz_localize(
            "UTC"
        ).dt.tz_convert("America/New_York").dt.strftime("%Y-%m-%d %H:%M:%S")

        min_d2, max_d2 = all_dt["date_obj"].min(), all_dt["date_obj"].max()

        g1, g2, g3, g4 = st.columns([1.2, 1.2, 1, 1])
        with g1:
            dt_start_d = st.date_input("From Date", value=min_d2, min_value=min_d2, max_value=max_d2, key="dtlog_start")
        with g2:
            dt_end_d = st.date_input("To Date", value=max_d2, min_value=min_d2, max_value=max_d2, key="dtlog_end")
        with g3:
            dt_pump_opts = ["All Pumps"] + sorted(all_dt["pump_station"].dropna().unique().tolist())
            g_pump = st.selectbox("Pump Station", dt_pump_opts, key="dtlog_pump")
        with g4:
            dt_reason_opts = ["All Reasons"] + sorted(all_dt["reason"].dropna().unique().tolist())
            g_reason = st.selectbox("Reason", dt_reason_opts, key="dtlog_reason")

        dt_matches = all_dt[(all_dt["date_obj"] >= dt_start_d) & (all_dt["date_obj"] <= dt_end_d)]
        if g_pump != "All Pumps":
            dt_matches = dt_matches[dt_matches["pump_station"] == g_pump]
        if g_reason != "All Reasons":
            dt_matches = dt_matches[dt_matches["reason"] == g_reason]
        dt_matches = dt_matches.sort_values(by="timestamp", ascending=False)

        st.caption(f"**{len(dt_matches)}** record(s) match the current filters.")
        st.markdown("---")

        if dt_matches.empty:
            st.info("No records match the current filters.")
        else:
            dt_show_n = st.number_input(
                "Rows to display (narrow filters or increase this to see more)",
                min_value=10, max_value=1000, value=max(10, min(100, len(dt_matches))), step=10, key="dtlog_show_n",
            )
            dt_visible = dt_matches.head(int(dt_show_n))

            hdr2 = st.columns([1.6, 1.1, 1.4, 1, 1.2, 0.7])
            for c, label in zip(hdr2, ["Timestamp", "Station", "Reason", "Minutes", "Operator", ""]):
                c.markdown(f"**{label}**")

            for _, row in dt_visible.iterrows():
                rc = st.columns([1.6, 1.1, 1.4, 1, 1.2, 0.7])
                rc[0].caption(str(row.get("timestamp_disp", row.get("timestamp", ""))))
                rc[1].caption(str(row.get("pump_station", "")))
                rc[2].caption(str(row.get("reason", "")))
                rc[3].caption(f"{int(row.get('duration_min', 0) or 0)}")
                rc[4].caption(str(row.get("operator_name", "")))
                if rc[5].button("🗑️", key=f"del_dtlog_{row['id']}", help=f"Delete downtime log #{row['id']}"):
                    delete_downtime_log(int(row["id"]))
                    st.toast(f"✅ Deleted downtime log #{int(row['id'])}")
                    st.rerun()

            if len(dt_matches) > len(dt_visible):
                st.caption(f"Showing {len(dt_visible)} of {len(dt_matches)} — increase 'Rows to display' above to see more.")

            st.markdown("---")
            with st.expander("☢️ Bulk Delete — every record matching the filters above"):
                st.caption(
                    f"This will permanently delete all **{len(dt_matches)}** downtime log record(s) currently "
                    "matched by the filters above, not just the ones visible on screen."
                )
                if _confirm_bulk_delete("dtlog_bulk", len(dt_matches)):
                    deleted2 = 0
                    for log_id in dt_matches["id"].tolist():
                        if delete_downtime_log(int(log_id)):
                            deleted2 += 1
                    st.success(f"✅ Deleted {deleted2} downtime log record(s).")
                    st.session_state.pop("dtlog_bulk_confirm_text", None)
                    st.rerun()
