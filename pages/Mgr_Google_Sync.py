import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from database import get_production_logs_df

st.set_page_config(page_title="Google Cloud Sync | Formlabs MES", page_icon="☁️", layout="wide")

st.markdown("""
<style>
    /* Aggressively hide native multi-page navigation to minimize load flash */
    [data-testid="stSidebarNav"], 
    [data-testid="stSidebarNav"] > ul {
        display: none !important;
        visibility: hidden !important;
        height: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Default Dark"), THEMES["Default Dark"]), unsafe_allow_html=True)

if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") not in ["manager", "admin"]:
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
import extra_streamlit_components as stx

# Initialize cookie manager for the logout function
cookie_manager = stx.CookieManager(key=f"ghost_cookie_{st.session_state.get('user_id', '0')}")
current_role = st.session_state.get("user_role", "operator")

# --- TOP NAVIGATION BAR ---
st.markdown("<br>", unsafe_allow_html=True)
if current_role == "admin":
    nav_1, nav_2, nav_3, nav_4, nav_5, nav_6 = st.columns(6, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
    with nav_6: st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)
elif current_role == "manager":
    nav_1, nav_2, nav_3, nav_4, nav_5 = st.columns(5, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
else:
    nav_1, nav_2, nav_3 = st.columns(3, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Workstation", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)

st.markdown("---")

# --- SIDEBAR: PROFILE & SETTINGS ---
with st.sidebar:
    st.markdown("---")
    st.markdown(f"### 👤 {st.session_state.get('user_name', 'Operator')}")
    st.caption(
        f"Role: `{str(st.session_state.get('user_role', 'unknown')).upper()}` | Shift: `{st.session_state.get('user_shift', 'Unknown')}`")

    # --- CUSTOM ROUTER (NEW) ---
    st.markdown("#### 🗺️ Navigation")
    st.page_link("Home.py", label="Live SCADA", icon="⚡")
    st.page_link("pages/Operator_Form.py", label="Operator Form", icon="📝")
    st.page_link("pages/Manager_Cockpit.py", label="Manager Cockpit", icon="📊")
    st.page_link("pages/Live_Reactors.py", label="Live Reactors", icon="🛢️")
    st.page_link("pages/Analytics_Hub.py", label="Analytics Hub", icon="🌌")

    # Only show IT Admin to actual admins
    if st.session_state.get("user_role") == "admin":
        st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️")

    st.markdown("---")
    # ---------------------------

    # UNIFIED SETTINGS POPOVER
    with st.popover("⚙️ Account & Preferences", use_container_width=True):
        set_tab1, set_tab2, set_tab3 = st.tabs(["🔑 Security", "🎨 Theme & Avatar", "💡 Feedback"])

        with set_tab1:
            st.markdown("#### Update Account Credentials")
            with st.form("user_cred_form"):
                acc_name = st.text_input("Full Display Name", value=st.session_state.get("user_name", ""))
                acc_user = st.text_input("Username / ID", value=st.session_state.get("username", ""))
                acc_pin = st.text_input("New PIN / Password", type="password", placeholder="Leave blank to keep current PIN")

                if st.form_submit_button("💾 Save Credentials", type="primary", use_container_width=True):
                    from database import update_user_credentials
                    success, msg = update_user_credentials(st.session_state["user_id"], acc_user, acc_pin, acc_name)
                    if success:
                        st.session_state["user_name"] = acc_name.strip()
                        st.session_state["username"] = acc_user.lower().strip()
                        st.success(f"✅ {msg}")

                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        with set_tab2:
            st.markdown("#### Interface Preferences")
            current_t = st.session_state.get("preferred_theme", "Default Dark")
            chosen_t = st.selectbox("System Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(current_t) if current_t in THEMES else 0)

            if chosen_t != current_t:
                from database import update_user_theme
                update_user_theme(st.session_state["user_id"], chosen_t)
                st.session_state["preferred_theme"] = chosen_t
                cookie_manager.set("formlabs_mes_theme", chosen_t, expires_at=datetime.now() + timedelta(days=365))
                st.rerun()

            st.markdown("---")
            st.markdown("#### Profile Picture")
            new_avatar = st.file_uploader("Upload Avatar", type=["png", "jpg", "jpeg", "webp"], key="set_avatar_upload")
            if st.button("💾 Save Avatar", type="primary", use_container_width=True):
                if new_avatar:
                    from database import update_user_avatar
                    update_user_avatar(st.session_state["user_id"], new_avatar)
                    st.toast("✅ Avatar updated!")
                    st.rerun()

        with set_tab3:
            st.markdown("#### Universal Feedback Box")
            with st.form("settings_sug_form", clear_on_submit=True):
                s_cat = st.selectbox("Category", ("Feature Request", "App Bug / Error", "Plant Floor Issue"))
                s_txt = st.text_area("Observation / Description")
                if st.form_submit_button("🚀 Submit Feedback", type="primary", use_container_width=True):
                    if s_txt.strip():
                        from database import add_suggestion
                        add_suggestion(st.session_state.get("user_name"), st.session_state.get("user_role"), s_cat, s_txt)
                        st.success("✅ Submitted to IT Admin!")

    st.markdown("<br>", unsafe_allow_html=True)

    if current_role in ["admin", "manager"]:
        st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        # 1. Save the current theme before wiping the session
        saved_theme = st.session_state.get("preferred_theme", "Default Dark")

        try:
            # 2. Forcing an expired date is much more reliable than just .delete()
            cookie_manager.set("formlabs_mes_token", "", expires_at=datetime.now() - timedelta(days=1))
            cookie_manager.delete("formlabs_mes_token")
        except Exception:
            pass

        # 3. Clear memory
        st.session_state.clear()

        # 4. Restore the theme and set a Hard Lockout flag!
        st.session_state["preferred_theme"] = saved_theme
        st.session_state["explicitly_logged_out"] = True

        st.switch_page("Home.py")
        st.rerun()

st.subheader("☁️ External Reporting & Google Cloud Sync Control Panel")
st.caption("Configure custom payload types, execution triggers, and metric filters to transmit plant telemetry directly to Google Sheets.")

df_logs = get_production_logs_df()

col_a, col_b = st.columns(2)
with col_a:
    export_mode = st.radio("1. Select Data Payload Type", ["📊 Aggregated Calculated Metrics (KPI Summary)", "📋 Raw Production Audit Stream"], key="mgr_gsheet_payload")
    sync_horizon = st.selectbox("2. Time Horizon Scope", ("⚡ Live Today (Active Shift)", "📆 Past 7 Days", "📊 Past 30 Days", "🌐 All Time History"))

with col_b:
    sync_trigger = st.radio("3. Automation Trigger Preference", ("👆 Manual On-Demand Push", "📤 Auto-Sync on Shift Handover", "⏱️ Scheduled Background Webhook"), key="mgr_gsheet_trigger")

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
        with st.spinner(f"Packaging payload and transmitting via {sync_trigger}..."):
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