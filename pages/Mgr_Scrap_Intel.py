
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
from database import get_production_logs_df, get_downtime_logs_df, do_logout

st.set_page_config(page_title="Scrap Intelligence | Formlabs MES", page_icon="📊", layout="wide")


try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Default Dark"), THEMES["Default Dark"]), unsafe_allow_html=True)

if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") not in ["manager", "admin"]:
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
from ui_shell import render_shell
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
    if not df_logs.empty:
        resin_grp = df_logs.groupby("resin_type")["bottles_filled"].sum().reset_index()
        fig_resin = px.bar(resin_grp, x="resin_type", y="bottles_filled", color="resin_type", title="Output by Formulation")
        fig_resin.update_layout(height=320, showlegend=False, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#94A3B8"))
        st.plotly_chart(fig_resin, use_container_width=True)
with c2:
    if not df_dt.empty:
        dt_grp = df_dt.groupby("reason")["duration_min"].sum().reset_index()
        fig_dt = px.pie(dt_grp, names="reason", values="duration_min", title="Downtime Reasons")
        fig_dt.update_layout(height=320, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font=dict(color="#94A3B8"))
        st.plotly_chart(fig_dt, use_container_width=True)
