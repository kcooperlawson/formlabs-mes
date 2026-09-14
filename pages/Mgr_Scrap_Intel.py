
import os
import sys

import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime, timedelta

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_production_logs_df, get_downtime_logs_df, get_all_resin_specs_df, do_logout
from resin_palette import resin_color_map, stored_color_map

st.set_page_config(page_title="Scrap Intelligence | Formlabs MES", page_icon="📊", layout="wide")


try:
    from themes import THEMES
except ImportError:
    THEMES = {"Formlabs Forge": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Formlabs Forge"), THEMES["Formlabs Forge"]), unsafe_allow_html=True)

# Restore the session before deciding whether to refuse it. Without this the
# role check below runs against an empty session on any cold load - a refresh,
# a bookmark, a link opened in a new tab - and answers Access Denied to a
# manager who has every right to be here. It only ever appeared to work
# because arriving from another page carried the session in memory, and the
# one thing nobody does while testing is press F5.
import extra_streamlit_components as _stx
from database import can
from database import check_authentication as _check_auth
_check_auth(_stx.CookieManager(key="auth_scrap_intel"))

if not st.session_state.get("authenticated", False) or not can("view_manager_cockpit"):
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
from ui_shell import render_shell
from components import empty_state
cookie_manager = render_shell()
current_role = st.session_state.get("user_role", "operator")

st.subheader("Quality Ops Canvas — Scrap Reject & FPY Engine")

df_logs = get_production_logs_df()
df_dt = get_downtime_logs_df()

s_col1, s_col2, s_col3, s_col4 = st.columns(4)
total_empty_scrap = df_logs["scrap_empty"].sum() if not df_logs.empty else 0
total_filled_scrap = df_logs["scrap_filled"].sum() if not df_logs.empty else 0
with s_col1: st.metric("Empty Bottles Scrapped", f"{total_empty_scrap} units")
with s_col2: st.metric("Filled Bottles Scrapped", f"{total_filled_scrap} units")
with s_col3: st.metric("Total Scrap Volume", f"{total_empty_scrap + total_filled_scrap} units")
with s_col4: st.metric("Yield Severity Status", "Optimal", delta="0% Resin Loss")

c1, c2 = st.columns(2)
with c1:
    if df_logs.empty:
        empty_state(
            "No production logged in this window",
            "Output by formulation appears here once operators start logging pouring. "
            "Widen the date range above if you are looking at a quiet period.",
            icon="🧪")
    if not df_logs.empty:
        resin_grp = df_logs.groupby("resin_type")["bottles_filled"].sum().reset_index()
        # Bars carry each resin's own colour instead of Plotly's default
        # sequence. A chart that invents its own palette teaches a second,
        # conflicting colour language for the same set of things.
        _bar_colours = resin_color_map(resin_grp["resin_type"].tolist(),
                                       stored_color_map(get_all_resin_specs_df("ALL")))
        fig_resin = px.bar(resin_grp, x="resin_type", y="bottles_filled", color="resin_type",
                           color_discrete_map=_bar_colours, title="Output by Formulation")
        fig_resin.update_layout(height=320, showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#94A3B8"))
        st.plotly_chart(fig_resin, use_container_width=True)
with c2:
    if df_dt.empty:
        empty_state(
            "No downtime recorded",
            "Every stoppage an operator logs is broken down here by reason, which is "
            "what turns a vague sense that a pump is troublesome into a ranked list.",
            action="Downtime is logged from the operator workstation, under Downtime.",
            icon="⏱️")
    if not df_dt.empty:
        dt_grp = df_dt.groupby("reason")["duration_min"].sum().reset_index()
        fig_dt = px.pie(dt_grp, names="reason", values="duration_min", title="Downtime Reasons")
        fig_dt.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#94A3B8"))
        st.plotly_chart(fig_dt, use_container_width=True)
