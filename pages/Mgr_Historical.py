

import os
import sys
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_production_logs_df, do_logout, get_all_users_df
from database import get_all_resin_specs_df
from resin_palette import resin_chip, stored_color_map

st.set_page_config(page_title="Historical Analytics | Formlabs MES", page_icon="📈", layout="wide")


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
_check_auth(_stx.CookieManager(key="auth_historical"))

if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") not in ["manager", "admin"]:
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
from ui_shell import render_shell
from components import empty_state
cookie_manager = render_shell()
current_role = st.session_state.get("user_role", "operator")

st.markdown("### 📈 Historical Plant Analytics & Production Trends")

df_logs = get_production_logs_df()

# Build operator dropdown from resolved identities: prefer each operator_id's
# CURRENT full_name so a mid-history rename shows one entry, not two. Any
# operator_name with no resolved operator_id (a deleted account, or a legacy
# name that never matched a real user) still gets its own entry so that data
# isn't silently hidden from the filter.
_users_df = get_all_users_df()
_id_to_name = dict(zip(_users_df["id"], _users_df["full_name"])) if not _users_df.empty else {}
_name_to_id = {v: k for k, v in _id_to_name.items()}

if not df_logs.empty:
    resolved_ids = df_logs["operator_id"].dropna().unique().tolist()
    resolved_names = sorted({_id_to_name[i] for i in resolved_ids if i in _id_to_name})
    unresolved_names = sorted(
        df_logs[df_logs["operator_id"].isna()]["operator_name"].dropna().unique().tolist()
    )
    operator_options = ["All Operators"] + resolved_names + unresolved_names
else:
    operator_options = ["All Operators"]

col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    date_range = st.selectbox("📅 Time Horizon", ["Past 7 Days", "Past 30 Days", "Year to Date", "All Time"])
with col_f2:
    selected_resin = st.selectbox("🧪 Resin Filter", ["All Resins"] + sorted(df_logs["resin_type"].dropna().unique().tolist()) if not df_logs.empty else ["All Resins"])
    if selected_resin and selected_resin != "All Resins":
        st.markdown(
            resin_chip(selected_resin, stored_color_map(get_all_resin_specs_df("ALL")).get(str(selected_resin))),
            unsafe_allow_html=True,
        )
with col_f3:
    selected_op = st.selectbox("👤 Operator Filter", operator_options)

today_d = date.today()
start_date_filter = None
if date_range == "Past 7 Days": start_date_filter = today_d - timedelta(days=7)
elif date_range == "Past 30 Days": start_date_filter = today_d - timedelta(days=30)
elif date_range == "Year to Date": start_date_filter = date(today_d.year, 1, 1)

# A selected name that resolves to a current user filters by operator_id (FK) —
# this pulls in every row tied to that person, even ones logged under an older
# name. A name with no resolution (deleted/legacy) falls back to an exact
# operator_name match, same as before.
selected_operator_id = _name_to_id.get(selected_op) if selected_op != "All Operators" else None
selected_operator_name = selected_op if (selected_op != "All Operators" and selected_operator_id is None) else None

hist_df = get_production_logs_df(
    start_date=start_date_filter, end_date=today_d, resin=selected_resin,
    operator=selected_operator_name, operator_id=selected_operator_id
)

if hist_df.empty:
    empty_state(
        "Nothing logged in this range",
        "Historical trends compare output, scrap and yield over time, so they need at "
        "least a few days of logs before the shape means anything.",
        action="Widen the date range, or clear the operator and resin filters above.",
        icon="📈")

if not hist_df.empty:
    hist_df['date_str'] = pd.to_datetime(hist_df['date']).dt.strftime('%Y-%m-%d')

pour_df = hist_df[hist_df["log_type"] == "Hourly Bottle Count"] if not hist_df.empty else pd.DataFrame()
pack_df = hist_df[hist_df["log_type"] == "Packing Count"] if not hist_df.empty else pd.DataFrame()
total_poured = pour_df["bottles_filled"].sum() if not pour_df.empty else 0
total_packed = pack_df["bottles_filled"].sum() if not pack_df.empty else 0
total_scrap = (pour_df["scrap_empty"].sum() + pour_df["scrap_filled"].sum()) if not pour_df.empty else 0
yield_pct = (total_poured / (total_poured + total_scrap) * 100) if (total_poured + total_scrap) > 0 else 100.0

k1, k2, k3, k4 = st.columns(4)
k1.metric("Total Units Poured", f"{total_poured:,}")
k2.metric("Total Units Packed", f"{total_packed:,}")
k3.metric("Total Scrap Units", f"{total_scrap:,}")
k4.metric("Average Yield", f"{yield_pct:.1f}%")
st.markdown("---")

if not pour_df.empty:
    c1, c2 = st.columns(2)
    with c1:
        trend_df = pour_df.groupby("date_str")["bottles_filled"].sum().reset_index()
        fig_trend = px.line(trend_df, x="date_str", y="bottles_filled", markers=True, title="Units Poured Over Time")
        fig_trend.update_layout(height=320, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94A3B8'))
        st.plotly_chart(fig_trend, use_container_width=True)
    with c2:
        _op_display = pour_df.copy()
        _op_display["display_operator"] = _op_display.apply(
            lambda r: _id_to_name.get(r.get("operator_id"), r["operator_name"]), axis=1
        )
        op_df = _op_display.groupby("display_operator")["bottles_filled"].sum().reset_index().sort_values("bottles_filled", ascending=False)
        fig_op = px.bar(op_df, x="display_operator", y="bottles_filled", color="display_operator", title="Total Output by Operator")
        fig_op.update_layout(height=320, showlegend=False, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94A3B8'))
        st.plotly_chart(fig_op, use_container_width=True)


