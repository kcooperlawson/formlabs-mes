
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from database import get_production_logs_df, do_logout

st.set_page_config(page_title="Google Cloud Sync | Formlabs MES", page_icon="☁️", layout="wide")


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

st.subheader("☁️ External Reporting & Google Cloud Sync Control Panel")
st.caption("Choose what to send and how far back, pick the columns, and push it to the plant's Google Sheet. Every push is manual and on demand.")

df_logs = get_production_logs_df()

# There was a third control here - "Automation Trigger Preference", offering a
# manual push, an auto-sync on shift handover, and a scheduled webhook. Only
# the first existed: the chosen value was never read except to word the
# spinner, so the other two produced the same manual push with a different
# sentence over it. A control that appears to configure something and does not
# is worse than no control - and one of its options named a screen that has
# since been removed for describing itself as more than it was, which is the
# same fault twice.
col_a, col_b = st.columns(2)
with col_a:
    export_mode = st.radio("1. Select Data Payload Type", ["📊 Aggregated Calculated Metrics (KPI Summary)", "📋 Raw Production Audit Stream"], key="mgr_gsheet_payload")

with col_b:
    sync_horizon = st.selectbox("2. Time Horizon Scope", ("⚡ Live Today (Active Shift)", "📆 Past 7 Days", "📊 Past 30 Days", "🌐 All Time History"))

st.markdown("---")
st.markdown("#### ⚙️ Payload Column Customization")

if export_mode == "📊 Aggregated Calculated Metrics (KPI Summary)":
    if not df_logs.empty:
        calc_df = df_logs.copy()
        calc_df["date_str"] = pd.to_datetime(calc_df["date"]).dt.strftime("%Y-%m-%d")

        def get_row_liters(r):
            b_count = float(r.get("bottles_filled", 0) or 0)
            c_type = str(r.get("cartridge_type", "V2")).strip().upper()
            vol_mult = 5.0 if "RPS" in c_type else (0.124 if "PIGMENT" in c_type else 1.0)
            return b_count * vol_mult

        calc_df["liters_calc"] = calc_df.apply(get_row_liters, axis=1)
        calc_df["total_scrap"] = calc_df["scrap_empty"].fillna(0) + calc_df["scrap_filled"].fillna(0)

        summary_df = calc_df.groupby(
            ["date_str", "shift", "resin_type", "cartridge_type", "operator_name", "pump_station"]
        ).agg(
            Total_Poured_Units=("bottles_filled", lambda x: x[calc_df.loc[x.index, "log_type"] == "Hourly Bottle Count"].sum()),
            Total_Packed_Units=("bottles_filled", lambda x: x[calc_df.loc[x.index, "log_type"] == "Packing Count"].sum()),
            Volume_Output_Liters=("liters_calc", lambda x: x[calc_df.loc[x.index, "log_type"] == "Hourly Bottle Count"].sum()),
            Total_Scrap_Units=("total_scrap", "sum"),
            Log_Count=("id", "count")
        ).reset_index()

        summary_df["Quality FPY (%)"] = (summary_df["Total_Poured_Units"] / (summary_df["Total_Poured_Units"] + summary_df["Total_Scrap_Units"]) * 100).fillna(100.0).round(2)
        summary_df["Scrap Rate (%)"] = (summary_df["Total_Scrap_Units"] / (summary_df["Total_Poured_Units"] + summary_df["Total_Scrap_Units"]) * 100).fillna(0.0).round(2)
        summary_df["Pending Floor WIP"] = (summary_df["Total_Poured_Units"] - summary_df["Total_Packed_Units"]).clip(lower=0)
        summary_df["Est Skids Built"] = (summary_df["Total_Packed_Units"] / 500.0).round(2)

        summary_df.rename(columns={
            "date_str": "Date", "shift": "Shift", "resin_type": "Resin Formulation",
            "cartridge_type": "Container Format", "operator_name": "Operator Name",
            "pump_station": "Pump Station", "Total_Poured_Units": "Units Poured",
            "Total_Packed_Units": "Units Packed", "Volume_Output_Liters": "Volume Output (Liters)",
            "Total_Scrap_Units": "Scrap Reject Units"
        }, inplace=True)

        export_payload_df = summary_df
    else:
        export_payload_df = pd.DataFrame()
else:
    if not df_logs.empty:
        export_payload_df = df_logs.drop(columns=[c for c in ["date_obj", "date_str"] if c in df_logs.columns]).copy()
    else:
        export_payload_df = pd.DataFrame()

available_metrics = list(export_payload_df.columns) if not export_payload_df.empty else []
selected_export_cols = st.multiselect("Toggle Metrics / Statistics to Include in Payload:", options=available_metrics, default=available_metrics)

st.markdown("<br>", unsafe_allow_html=True)
if st.button("🚀 Execute Google Sheets Transmission", type="primary", use_container_width=True):
    google_url = os.getenv("GOOGLE_SHEETS_WEBHOOK")
    if not google_url:
        st.error("⚠️ Webhook missing! Please ensure GOOGLE_SHEETS_WEBHOOK is set in your .env file.")
    elif not selected_export_cols:
        st.warning("⚠️ Please select at least one metric column to export.")
    elif df_logs.empty:
        st.warning("⚠️ No production data currently exists in the database to sync.")
    else:
        with st.spinner("Packaging payload and transmitting..."):
            try:
                import requests
                final_df = export_payload_df[selected_export_cols].copy().astype(str)
                payload = final_df.to_dict(orient="records")
                target_tab = "KPI Summary" if "Aggregated" in export_mode else "Raw Audit Logs"
                wrapped_payload = {"sheet_name": target_tab, "data": payload}
                response = requests.post(google_url, json=wrapped_payload)
                if response.status_code == 200:
                    st.success(f"✅ Dispatched {len(final_df)} records to tab '{target_tab}' in Google Sheets!")
                else:
                    st.error(f"❌ Transmission Failed ({response.status_code}): {response.text}")
            except Exception as e:
                st.error(f"❌ Transmission Error: {str(e)}")
