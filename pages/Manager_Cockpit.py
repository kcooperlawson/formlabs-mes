import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv

load_dotenv()
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date, timedelta
import time
from database import (
    get_production_logs_df,
    get_downtime_logs_df,
    get_assigned_runs_df,
    create_assigned_run,
    update_assigned_run_progress,
    update_run_status,
    delete_assigned_run,
    sync_all_runs_with_logs,
    get_all_resin_specs_df,
    bulk_update_resin_specs,
    get_all_pumps_df,
    add_pump_station,
    delete_pump_station,
    get_downtime_reasons,
    add_downtime_reason,
    delete_downtime_reason,
    get_all_users_df,
    get_active_operators,
    get_active_pumps,
    create_user,
    delete_user,
    get_cleanliness_audits_df,
    delete_production_log,
    delete_downtime_log,
    delete_cleanliness_audit,
    get_plant_settings,
    update_plant_settings,
    update_user_target,
    update_user_pin,
    get_all_reactors_df,
    update_pump_status,
    restore_database_backup,
    create_database_backup,
    complete_run_with_custom_total,
    send_floor_message,
    get_chat_history_df,
    get_operators_with_messages,
    get_todays_checklists_df,
    BACKUP_DIR,
    UPLOAD_DIR,
    update_user_role_and_shift,
    update_user_pin,
    delete_user_by_username,
    add_resin_spec,
    delete_resin_spec,
    add_suggestion,
)

st.set_page_config(page_title="Manager Work Order Dispatch & Cockpit | Formlabs MES", page_icon="📊", layout="wide")

# ===================== DYNAMIC THEME INJECTION =====================
try:
    from themes import THEMES
except ImportError:
    THEMES = {
        "Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
if active_theme not in THEMES:
    active_theme = "Default Dark"

st.markdown(THEMES[active_theme], unsafe_allow_html=True)
st.logo("assets/formlabs_logo.png")

# --- PERSISTENT AUTO-LOGIN ENGINE & SECURITY GATE ---
import extra_streamlit_components as stx

cookie_manager = stx.CookieManager(key="mgr_cookies")

# Initialize our double-take flag
if "auth_check_passed" not in st.session_state:
    st.session_state["auth_check_passed"] = False

if not st.session_state.get("authenticated", False):
    cached_token = cookie_manager.get(cookie="formlabs_mes_token")

    if cached_token is not None:
        from database import get_all_users_df

        df_users = get_all_users_df()
        user_match = df_users[df_users["username"] == cached_token]

        if not user_match.empty:
            user_data = user_match.iloc[0]
            st.session_state["authenticated"] = True
            st.session_state["user_id"] = int(user_data["id"])
            st.session_state["user_role"] = user_data["role"]
            st.session_state["user_name"] = user_data["full_name"]
            st.session_state["user_shift"] = user_data.get("shift", "Shift 1")
            st.session_state["preferred_theme"] = user_data.get("preferred_theme", "Default Dark")
            time.sleep(0.2)
            st.rerun()
    else:
        # THE DOUBLE-TAKE: Give the browser 0.2 seconds to send the cookie!
        if not st.session_state["auth_check_passed"]:
            st.session_state["auth_check_passed"] = True
            time.sleep(0.2)
            st.rerun()
        else:
            # If it checked twice and STILL no cookie, they are truly logged out.
            st.warning("🔒 Session Expired. Please log in.")
            st.switch_page("Home.py")
            st.stop()

# ===================== SIDEBAR: PROFILE & SETTINGS =====================
with st.sidebar:
    st.markdown("---")
    st.markdown(f"### 👤 {st.session_state.get('user_name', 'Operator')}")
    st.caption(
        f"Role: `{str(st.session_state.get('user_role', 'unknown')).upper()}` | Shift: `{st.session_state.get('user_shift', 'Unknown')}`")

    # UNIFIED SETTINGS POPOVER
    with st.popover("⚙️ Account & Preferences", use_container_width=True):
        set_tab1, set_tab2, set_tab3 = st.tabs(["🔑 Security", "🎨 Theme & Avatar", "💡 Feedback"])

        # TAB 1: USERNAME & PIN
        with set_tab1:
            st.markdown("#### Update Account Credentials")
            with st.form("user_cred_form"):
                acc_name = st.text_input("Full Display Name", value=st.session_state.get("user_name", ""))
                acc_user = st.text_input("Username / ID", value=st.session_state.get("username", ""))
                acc_pin = st.text_input("New PIN / Password", type="password",
                                        placeholder="Leave blank to keep current PIN")

                if st.form_submit_button("💾 Save Credentials", type="primary", use_container_width=True):
                    from database import update_user_credentials

                    success, msg = update_user_credentials(
                        user_id=st.session_state["user_id"],
                        new_username=acc_user,
                        new_pin=acc_pin,
                        new_fullname=acc_name
                    )
                    if success:
                        st.session_state["user_name"] = acc_name.strip()
                        st.session_state["username"] = acc_user.lower().strip()
                        st.success(f"✅ {msg}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        # TAB 2: THEME & AVATAR
        with set_tab2:
            st.markdown("#### Interface Preferences")
            current_t = st.session_state.get("preferred_theme", "Default Dark")
            chosen_t = st.selectbox("System Theme", list(THEMES.keys()),
                                    index=list(THEMES.keys()).index(current_t) if current_t in THEMES else 0)

            if chosen_t != current_t:
                from database import update_user_theme

                update_user_theme(st.session_state["user_id"], chosen_t)
                st.session_state["preferred_theme"] = chosen_t
                st.rerun()

            st.markdown("---")
            st.markdown("#### Profile Picture")
            new_avatar = st.file_uploader("Upload Avatar", type=["png", "jpg", "jpeg", "webp"], key="set_avatar_upload")
            if st.button("💾 Save Avatar", type="primary", use_container_width=True):
                if new_avatar:
                    from database import update_user_avatar

                    update_user_avatar(st.session_state["user_id"], new_avatar)
                    st.success("✅ Avatar updated!")
                    time.sleep(1)
                    st.rerun()

        # TAB 3: FEEDBACK & CHANGELOG
        with set_tab3:
            st.markdown("#### Universal Feedback Box")
            with st.form("settings_sug_form", clear_on_submit=True):
                s_cat = st.selectbox("Category", ("Feature Request", "App Bug / Error", "Plant Floor Issue"))
                s_txt = st.text_area("Observation / Description")
                if st.form_submit_button("🚀 Submit Feedback", type="primary", use_container_width=True):
                    if s_txt.strip():
                        from database import add_suggestion

                        add_suggestion(st.session_state.get("user_name"), st.session_state.get("user_role"), s_cat,
                                       s_txt)
                        st.success("✅ Submitted to IT Admin!")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- LAUNCH TV MODE ---
    current_role = st.session_state.get("user_role", "operator")
    if current_role in ["admin", "manager"]:
        st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        # 1. Catch missing cookie errors gracefully
        try:
            cookie_manager.delete("formlabs_mes_token")
        except Exception:
            pass

        # 2. Clear authentication and session state
        st.session_state["authenticated"] = False
        st.session_state.clear()

        # 3. Force immediate redirect to the Home login page
        st.switch_page("Home.py")
        time.sleep(0.5)
        st.rerun()



# ===================== MAIN COCKPIT UI =====================
import base64


def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""


logo_b64 = get_base64_image("assets/formlabs_logo.png")

# ===================== ROLE-BASED TOP NAVIGATION =====================
current_role = st.session_state.get("user_role", "operator")

st.markdown("<br>", unsafe_allow_html=True)
if current_role == "admin":
    # God Mode (Now 6 Columns)
    nav_1, nav_2, nav_3, nav_4, nav_5, nav_6 = st.columns(6, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
    with nav_6: st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)
elif current_role == "manager":
    # Manager Suite (Now 5 Columns)
    nav_1, nav_2, nav_3, nav_4, nav_5 = st.columns(5, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
else:
    # Operator View (Stays 3 Columns)
    nav_1, nav_2, nav_3 = st.columns(3, gap="small")
    with nav_1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2: st.page_link("pages/Operator_Form.py", label="Workstation", icon="📝", use_container_width=True)
    with nav_3: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)

st.markdown("---")

st.markdown(f"""
<div style="display:flex; align-items:center; margin-bottom: 5px;">
    <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain; margin-right: 15px;">
    <h1 style="margin:0; padding:0; font-size: 2.2rem;">📊 Plant Manager Operations & Work Order Dispatch</h1>
</div>
""", unsafe_allow_html=True)
st.caption("Reactor Tank Allocation, Assigned Runs Dispatch, Resin Lookup & Staff Roster")


df_logs = get_production_logs_df()
df_dt = get_downtime_logs_df()
df_runs = get_assigned_runs_df()
df_pumps = get_all_pumps_df()
df_users = get_all_users_df()
df_audits = get_cleanliness_audits_df()
active_operators_list = get_active_operators()
active_pumps_list = get_active_pumps()
df_reactors = get_all_reactors_df()

# ===================== BULLETPROOF TAB PILL STYLING =====================
st.markdown("""
<style>
    /* Hide Streamlit's default red underline and bottom border */
    [data-testid="stTabs"] [data-baseweb="tab-highlight"],
    [data-testid="stTabs"] [data-baseweb="tab-border"] {
        display: none !important;
    }

    /* Tab Bar Container: Enable smooth horizontal scrolling */
    [data-testid="stTabs"] [data-baseweb="tab-list"] {
        display: flex !important;
        gap: 8px !important;
        background-color: transparent !important;
        overflow-x: auto !important;
        padding-bottom: 8px !important;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1) !important;
    }

    /* Inactive Tab Pills */
    [data-testid="stTabs"] button[data-baseweb="tab"] {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: 20px !important;
        padding: 8px 18px !important;
        white-space: nowrap !important;
        transition: all 0.2s ease-in-out !important;
    }

    /* Hover State */
    [data-testid="stTabs"] button[data-baseweb="tab"]:hover {
        background-color: rgba(255, 255, 255, 0.15) !important;
        border-color: rgba(255, 255, 255, 0.3) !important;
    }

    /* Active Selected Tab Pill */
    [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] {
        background-color: rgba(234, 88, 12, 0.25) !important;
        border: 1px solid #EA580C !important;
        box-shadow: 0 0 12px rgba(234, 88, 12, 0.4) !important;
    }

    /* Force text inside tab buttons to be large and styled */
    [data-testid="stTabs"] button[data-baseweb="tab"] p,
    [data-testid="stTabs"] button[data-baseweb="tab"] span {
        color: #94A3B8 !important;
        font-size: 0.95rem !important;
        font-weight: 700 !important;
    }

    [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] p,
    [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] span {
        color: #FFFFFF !important;
        font-weight: 900 !important;
    }
</style>
""", unsafe_allow_html=True)

# Modern, native Pill Selector
tab1, tab2, tab3, tab4, tab_hist, tab_chat, tab_roster, tab_gsheet, tab_handoff = st.tabs((
    "🎯 Assigned Runs", "⚖️ Resin Canvas", "📊 Scrap & Yield Intelligence",
    "📸 Cleanliness & Photo Gallery", "📈 Historical Analytics",
    "💬 Floor Comms", "👥 Roster", "☁️ Google Sync", "📤 Shift Handover"
))



# ===================== TAB 1: ASSIGNED RUNS & REACTOR DISPATCH =====================
with tab1:
    st.subheader("🎯 Fleet Production Progress & Work Order Dispatch")

    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    total_target = df_runs["target_units"].sum() if not df_runs.empty else 0
    total_actual = df_runs["current_units"].sum() if not df_runs.empty else 0
    fleet_pct = (total_actual / total_target * 100) if total_target > 0 else 0
    active_runs_count = len(df_runs[df_runs["status"].isin(["Active", "Pouring"])]) if not df_runs.empty else 0
    queued_count = len(df_runs[df_runs["status"] == "Queued"]) if not df_runs.empty else 0
    done_count = len(df_runs[df_runs["status"] == "Done"]) if not df_runs.empty else 0

    with col_k1:
        st.metric("Fleet Production Progress", f"{total_actual:,} / {total_target:,} units",
                  delta=f"{fleet_pct:.1f}% Completed")
    with col_k2:
        st.metric("Active Runs Status", f"{active_runs_count} Active",
                  delta=f"{queued_count} Queued | {done_count} Done")
    with col_k3:
        st.metric("Tracked Pumps", f"{len(df_pumps)} Configured",
                  delta=f"{len(df_runs['pump_station'].unique())} In Use")
    with col_k4:
        st.metric("Active Operators", f"{len(active_operators_list)} Ready", delta="Live Machine Sync")

    st.markdown("---")

    with st.expander("➕ Create & Assign New Work Order", expanded=True):
        st.markdown("##### 📋 Work Order Type")

        plant_config = get_plant_settings()
        if plant_config.get("enable_packing", True):
            run_type_selection = st.radio("Dispatch Type", ("Pouring", "Packing"), horizontal=True)
        else:
            run_type_selection = "Pouring"
            st.info("📦 Packing Module is currently disabled in Plant Settings.")

        with st.form("create_run_dispatch_form"):
            if run_type_selection == "Pouring":
                st.markdown("##### 🛢️ 1. Reactor Vessel & Tank Configuration")
                r_c1, r_c2, r_c3 = st.columns(3)
                with r_c1:
                    reactor_list = df_reactors["reactor_name"].tolist() if not df_reactors.empty else [
                        "No Reactors Configured"]
                    reactor_id = st.selectbox("Reactor Tank", reactor_list)
                with r_c2:
                    reactor_size_val = int(
                        df_reactors[df_reactors["reactor_name"] == reactor_id]["max_capacity_l"].iloc[
                            0]) if not df_reactors.empty else 5000
                    st.info(f"Capacity: {reactor_size_val:,} L")
                with r_c3:
                    lot_number = st.text_input("Batch Lot ID", value=f"LOT-{datetime.now().strftime('%Y%m%d')}-01")
            else:
                st.markdown("##### 📦 1. Packing Source Information")
                r_c1, r_c3 = st.columns([1, 2])
                with r_c1:
                    st.info("Source: Floor WIP (Unpacked Units)")
                    reactor_id = "Floor WIP"
                    reactor_size_val = 0
                with r_c3:
                    lot_number = st.text_input("Batch Lot ID to Pack",
                                               value=f"LOT-{datetime.now().strftime('%Y%m%d')}-01")

            st.markdown("##### 🧪 2. Resin Material & Packaging Target")
            m_c1, m_c2, m_c3 = st.columns(3)
            with m_c1:
                cartridge_type = st.selectbox("Container Format",
                                              ("V2 (1L Cartridge)", "V1 (1L Cartridge)", "RPS (5L Bulk Jug)",
                                               "Pigment"))
                cart_code = "RPS" if "RPS" in cartridge_type else (
                    "V1" if "V1" in cartridge_type else ("Pigment" if "Pigment" in cartridge_type else "V2"))
            with m_c2:
                specs_df = get_all_resin_specs_df(cart_code)
                if specs_df.empty:
                    specs_df = get_all_resin_specs_df("ALL")
                resin_list = sorted(specs_df["resin_name"].unique().tolist())
                selected_resin = st.selectbox("Resin Formulation", resin_list)
            with m_c3:
                if run_type_selection == "Pouring":
                    default_target = int(reactor_size_val / 5.0) if cart_code == "RPS" else int(reactor_size_val / 1.0)
                else:
                    default_target = 500
                target_units = st.number_input("Target Units", min_value=1, max_value=50000, value=default_target,
                                               step=50)

            st.markdown("##### 👤 3. Station & Personnel Assignment")
            s_c1, s_c2, s_c3 = st.columns(3)
            with s_c1:
                assigned_pump = st.selectbox("Assigned Station", active_pumps_list)
            with s_c2:
                target_role = "packer" if run_type_selection == "Packing" else "operator"
                if not df_users.empty:
                    personnel_list = df_users[df_users["role"] == target_role]["full_name"].tolist()
                    if len(personnel_list) == 0:
                        personnel_list = [f"No {target_role}s found in roster"]
                else:
                    personnel_list = ["Keagan C."]
                assigned_op = st.selectbox("Assigned Personnel", personnel_list)
            with s_c3:
                initial_status = st.selectbox("Initial Run Status", ("Active", "Queued"))
                status_code = "Active" if "Active" in initial_status else "Queued"

            run_notes = st.text_input("Special Process Instructions / Run Notes",
                                      placeholder="e.g. Needs updated warning labels.")
            submit_label = "🚀 Dispatch Pouring Run" if run_type_selection == "Pouring" else "📦 Dispatch Packing Run"

            if st.form_submit_button(submit_label, type="primary", use_container_width=True):
                auto_detected = create_assigned_run(
                    reactor_id=reactor_id, reactor_size_l=reactor_size_val, resin_type=selected_resin,
                    cartridge_type=cart_code, target_units=int(target_units), assigned_operator=assigned_op,
                    pump_station=assigned_pump, lot_number=lot_number, notes=run_notes, status=status_code,
                    run_type=run_type_selection
                )
                if auto_detected > 0:
                    st.success(f"✅ Dispatched {selected_resin}! Auto-detected {auto_detected:,} units already logged.")
                else:
                    st.success(
                        f"✅ Dispatched new {run_type_selection} run for {selected_resin} ({target_units:,} units) to {assigned_op}!")
                st.balloons()
                time.sleep(1.5)
                st.rerun()

    active_tab, completed_tab = st.tabs(["🚀 Active & Queued Runs", "✅ Completed Work Orders"])

    with active_tab:
        h_col1, h_col2 = st.columns((3, 1))
        with h_col1:
            st.markdown("### 📋 Active & Queued Assigned Runs")
        with h_col2:
            if st.button("🔄 Sync Progress with Logs", use_container_width=True):
                sync_all_runs_with_logs()
                st.success("✅ Synchronized run progress with production logs!")
                st.rerun()

        active_df = df_runs[df_runs["status"] != "Done"] if not df_runs.empty else pd.DataFrame()
        if not active_df.empty:
            for _, run in active_df.iterrows():
                with st.container():
                    prog_pct = min(1.0, run["current_units"] / run["target_units"]) if run["target_units"] > 0 else 0.0
                    status_color = "#10B981" if run["status"] in ["Active", "Pouring"] else (
                        "#F59E0B" if run["status"] == "Queued" else "#64748B")

                    st.markdown(f"""
                    <div style="background:#0D1627; border:1px solid #1E2B45; border-radius:8px; padding:16px; margin-bottom:12px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="background:{status_color}; color:#FFFFFF; font-size:0.75rem; font-weight:800; padding:2px 8px; border-radius:4px;">● {run['status'].upper()}</span>
                                <span style="font-size:1.15rem; font-weight:800; color:#FFFFFF; margin-left:8px;">{run['resin_type']}</span>
                                <span style="color:#00D2FF; font-weight:700; font-size:0.85rem; margin-left:6px;">[{run['cartridge_type']}]</span>
                            </div>
                            <div style="color:#94A3B8; font-size:0.85rem;">
                                🛢️ <b>{run.get('reactor_id', 'Reactor 1')}</b> ({run.get('reactor_size_l', 5000):,} L) &nbsp;|&nbsp; 🏷️ <b>{run['pump_station']}</b> &nbsp;|&nbsp; 👤 <b>{run['assigned_operator']}</b>
                            </div>
                        </div>
                    </div>
                    """, unsafe_allow_html=True)

                    st.progress(prog_pct,
                                text=f"Output: {run['current_units']:,} / {run['target_units']:,} Units ({prog_pct * 100:.1f}%) | Lot: {run.get('lot_number', 'N/A')}")

                    b_c1, b_c2, b_c3, b_c4 = st.columns(4)
                    with b_c1:
                        if st.button("+50 Units", key=f"p50_{run['id']}", use_container_width=True):
                            update_assigned_run_progress(run['id'], 50)
                            st.rerun()
                    with b_c2:
                        if st.button("+100 Units", key=f"p100_{run['id']}", use_container_width=True):
                            update_assigned_run_progress(run['id'], 100)
                            st.rerun()
                    with b_c3:
                        if run["status"] == "Queued":
                            if st.button("▶️ Start", key=f"start_{run['id']}", use_container_width=True):
                                update_run_status(run['id'], "Active")
                                st.rerun()
                        else:
                            if st.button("⏸️ Queue", key=f"queue_{run['id']}", use_container_width=True):
                                update_run_status(run['id'], "Queued")
                                st.rerun()
                    with b_c4:
                        if st.button("🗑️ Delete", key=f"del_run_{run['id']}", use_container_width=True):
                            delete_assigned_run(run['id'])
                            st.warning(f"Deleted Work Order #{run['id']}")
                            st.rerun()

                            # --- MANUAL OVERRIDE FOR 2ND SHIFT FINAL COUNT ---
                            with st.expander(f"⚙️ Set Final Count & Close Work Order #{run['id']}"):
                                with st.form(f"custom_complete_form_{run['id']}"):
                                    final_input_val = st.number_input(
                                        "Final Total Units Produced (Adjust for 2nd Shift)",
                                        value=int(run["current_units"]), step=10)
                                    if st.form_submit_button("💾 Save Final Count & Archive Run", type="primary"):
                                        complete_run_with_custom_total(run['id'], int(final_input_val))
                                        reconcile_pouring_to_packing(str(run['lot_number']), int(final_input_val))
                                        st.success(
                                            f"Work Order #{run['id']} finalized at {final_input_val} units, reactor emptied, and logs auto-reconciled!")
                                        st.rerun()
                    st.markdown("---")
        else:
            st.info("No assigned runs currently active.")

    with completed_tab:
        st.markdown("### 📚 Completed Work Order History")
        comp_df = df_runs[df_runs["status"] == "Done"].copy() if not df_runs.empty else pd.DataFrame()
        if not comp_df.empty:
            comp_df["created_at"] = pd.to_datetime(comp_df["created_at"]).dt.tz_localize("UTC").dt.tz_convert(
                "America/New_York").dt.strftime("%Y-%m-%d %H:%M:%S")
            cf1, cf2, cf3 = st.columns(3)
            with cf1:
                f_type = st.selectbox("Run Type Filter", ["All", "Pouring", "Packing"])
            with cf2:
                op_list = ["All"] + sorted(
                    comp_df["assigned_operator"].dropna().unique().tolist()); f_op = st.selectbox("Operator Filter",
                                                                                                  op_list)
            with cf3:
                lot_list = ["All"] + sorted(comp_df["lot_number"].astype(str).unique().tolist()); f_lot = st.selectbox(
                    "Lot Number Filter", lot_list)

            if f_type != "All": comp_df = comp_df[comp_df["run_type"] == f_type]
            if f_op != "All": comp_df = comp_df[comp_df["assigned_operator"] == f_op]
            if f_lot != "All": comp_df = comp_df[comp_df["lot_number"] == f_lot]

            if not comp_df.empty:
                display_cols = ["id", "created_at", "run_type", "resin_type", "cartridge_type", "lot_number",
                                "target_units", "current_units", "assigned_operator", "pump_station"]
                st.markdown(f'<div style="overflow-x: auto;">{comp_df[display_cols].to_html(index=False)}</div>',
                            unsafe_allow_html=True)
            else:
                st.info("No completed orders match the current filters.")
        else:
            st.info("No completed work orders logged yet.")

# ===================== TAB 2: INTERACTIVE LOOKUP CANVAS =====================
with tab2:
    st.subheader("⚖️ Formlabs Master Resin Specification Lookup Table")

    # --- ADD NEW PROPRIETARY RESIN FORM ---
    with st.expander("➕ Add New Proprietary Resin Formulation", expanded=False):
        with st.form("add_new_resin_form", clear_on_submit=True):
            a_c1, a_c2, a_c3 = st.columns(3)
            with a_c1:
                new_cart_type = st.selectbox("Container Format", ["V2", "V1", "V1/V2", "RPS", "Pigment", "Amazon"])
                new_sku = st.text_input("SKU Code", placeholder="e.g. RS-F2-CUST-01")
            with a_c2:
                new_resin_name = st.text_input("Formulation Name", placeholder="e.g. High-Temp Clear V3")
                new_code = st.text_input("Internal Resin Code", placeholder="e.g. FLCUST01")
            with a_c3:
                new_target_g = st.number_input("Target Fill Weight (g)", min_value=1.0, value=1110.0, step=10.0)
                new_min_g = st.number_input("Min Weight Tolerance (g)", min_value=1.0, value=1100.0, step=10.0)
                new_max_g = st.number_input("Max Weight Tolerance (g)", min_value=1.0, value=1125.0, step=10.0)

            if st.form_submit_button("💾 Save New Resin to Database", type="primary", use_container_width=True):
                if new_resin_name.strip():
                    if add_resin_spec(new_cart_type, new_sku, new_code, new_resin_name, new_target_g, new_min_g,
                                      new_max_g):
                        st.success(f"✅ Successfully registered '{new_resin_name}' in PostgreSQL!")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("❌ Failed to add resin. Check for duplicate names.")
                else:
                    st.warning("⚠️ Formulation name is required.")

    # --- FILTER BUTTONS ---
    c_all, c_v1, c_v12, c_v2, c_rps, c_pig, c_amz = st.columns(7)
    with c_all:
        fmt_all = st.button("🌐 ALL", use_container_width=True)
    with c_v1:
        fmt_v1 = st.button("🔵 V1 (1L)", use_container_width=True)
    with c_v12:
        fmt_v12 = st.button("🟢 V1/V2 Dual", use_container_width=True)
    with c_v2:
        fmt_v2 = st.button("🟠 V2 (1L)", use_container_width=True)
    with c_rps:
        fmt_rps = st.button("🍏 RPS (5L Jugs)", use_container_width=True)
    with c_pig:
        fmt_pig = st.button("🔴 Pigments", use_container_width=True)
    with c_amz:
        fmt_amz = st.button("🟡 Amazon Formulations", use_container_width=True)

    if "spec_filter" not in st.session_state: st.session_state["spec_filter"] = "ALL"
    if fmt_all:
        st.session_state["spec_filter"] = "ALL"
    elif fmt_v1:
        st.session_state["spec_filter"] = "V1"
    elif fmt_v12:
        st.session_state["spec_filter"] = "V1/V2"
    elif fmt_v2:
        st.session_state["spec_filter"] = "V2"
    elif fmt_rps:
        st.session_state["spec_filter"] = "RPS"
    elif fmt_pig:
        st.session_state["spec_filter"] = "Pigment"
    elif fmt_amz:
        st.session_state["spec_filter"] = "Amazon"

    curr_filter = st.session_state["spec_filter"]
    specs_filtered = get_all_resin_specs_df(curr_filter)
    s_c1, s_c2 = st.columns((3, 1))
    with s_c1:
        search_query = st.text_input("🔍 Quick Search by SKU, Resin Name, or Code")
    with s_c2:
        st.markdown(
            f"<br><span style='color:#38BDF8; font-weight:700;'>Showing: {curr_filter} ({len(specs_filtered)} Resins)</span>",
            unsafe_allow_html=True)

    if search_query.strip():
        specs_filtered = specs_filtered[
            specs_filtered["resin_name"].str.contains(search_query, case=False, na=False) |
            specs_filtered["sku"].str.contains(search_query, case=False, na=False) |
            specs_filtered["resin_code"].str.contains(search_query, case=False, na=False)
            ]

    if not specs_filtered.empty:
        specs_filtered["calculated_kg"] = (specs_filtered["actual_spec_g"] / 1000.0).round(4)
        display_specs = specs_filtered[
            ["id", "cartridge_type", "sku", "resin_code", "resin_name", "actual_spec_g", "min_weight_g", "max_weight_g",
             "calculated_kg", "multiplier", "lifetime_months"]]
        st.markdown(f'<div style="overflow-x: auto;">{display_specs.to_html(index=False)}</div>',
                    unsafe_allow_html=True)
    else:
        st.info("No resins found for the current filter.")

    # --- EDIT & DELETE FORMULATIONS ---
    with st.expander("✏️ Edit or Delete Resin Specifications"):
        all_specs_df = get_all_resin_specs_df("ALL")
        if not all_specs_df.empty:
            selected_spec_name = st.selectbox("Select Formulation", all_specs_df["resin_name"].tolist())
            spec_row = all_specs_df[all_specs_df["resin_name"] == selected_spec_name].iloc[0]
            spec_id = int(spec_row["id"])

            e_col1, e_col2 = st.columns([3, 1])
            with e_col1:
                with st.form(f"edit_spec_form_{spec_id}"):
                    ec1, ec2, ec3 = st.columns(3)
                    with ec1: new_spec = st.number_input("Target Spec (g)", value=float(spec_row["actual_spec_g"]),
                                                         step=5.0)
                    with ec2: new_min = st.number_input("Min Weight (g)", value=float(spec_row["min_weight_g"]),
                                                        step=5.0)
                    with ec3: new_max = st.number_input("Max Weight (g)", value=float(spec_row["max_weight_g"]),
                                                        step=5.0)
                    if st.form_submit_button("💾 Save Specification Update", type="primary", use_container_width=True):
                        bulk_update_resin_specs(pd.DataFrame(
                            [{"id": spec_id, "sku": spec_row["sku"], "resin_code": spec_row["resin_code"],
                              "resin_name": spec_row["resin_name"], "actual_spec_g": new_spec, "min_weight_g": new_min,
                              "max_weight_g": new_max, "multiplier": spec_row["multiplier"],
                              "lifetime_months": spec_row["lifetime_months"]}]))
                        st.success(f"✅ Updated tolerances for {selected_spec_name}!")
                        st.rerun()
            with e_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button(f"🗑️ Delete {selected_spec_name}", type="primary", use_container_width=True):
                    delete_resin_spec(spec_id)
                    st.success(f"Deleted '{selected_spec_name}'!")
                    time.sleep(1)
                    st.rerun()

# ===================== TAB 3: SCRAP & YIELD INTELLIGENCE =====================
with tab3:
    st.subheader("Quality Ops Canvas — Scrap Reject & FPY Engine")
    s_col1, s_col2, s_col3, s_col4 = st.columns(4)
    total_empty_scrap = df_logs["scrap_empty"].sum() if not df_logs.empty else 0
    total_filled_scrap = df_logs["scrap_filled"].sum() if not df_logs.empty else 0
    with s_col1:
        st.metric("Empty Bottles Scrapped", f"{total_empty_scrap} units")
    with s_col2:
        st.metric("Filled Bottles Scrapped", f"{total_filled_scrap} units")
    with s_col3:
        st.metric("Total Scrap Volume", f"{total_empty_scrap + total_filled_scrap} units")
    with s_col4:
        st.metric("Yield Severity Status", "Optimal", delta="0% Resin Loss")

    c1, c2 = st.columns(2)
    with c1:
        if not df_logs.empty:
            resin_grp = df_logs.groupby("resin_type")["bottles_filled"].sum().reset_index()
            fig_resin = px.bar(resin_grp, x="resin_type", y="bottles_filled", color="resin_type",
                               title="Output by Formulation")
            fig_resin.update_layout(height=320, showlegend=False)
            st.plotly_chart(fig_resin, use_container_width=True)
    with c2:
        if not df_dt.empty:
            dt_grp = df_dt.groupby("reason")["duration_min"].sum().reset_index()
            fig_dt = px.pie(dt_grp, names="reason", values="duration_min", title="Downtime Reasons")
            fig_dt.update_layout(height=320)
            st.plotly_chart(fig_dt, use_container_width=True)

# ===================== TAB 4: CLEANLINESS & PHOTO GALLERY =====================
with tab4:
    st.subheader("📸 Cleanliness & Station Photo Gallery")
    k1, k2, k3, k4, k5 = st.columns(5)
    total_audits = len(df_audits) if not df_audits.empty else 0
    start_checks = len(df_audits[df_audits["audit_type"].str.contains("Start", na=False)]) if not df_audits.empty else 0
    end_checks = len(df_audits[df_audits["audit_type"].str.contains("End", na=False)]) if not df_audits.empty else 0
    transfers = len(df_audits[df_audits["audit_type"].str.contains("Transfer", na=False)]) if not df_audits.empty else 0
    spills = len(df_audits[df_audits["is_spill"] == "Yes"]) if not df_audits.empty else 0
    with k1:
        st.metric("All Photo Audits", f"{total_audits} records")
    with k2:
        st.metric("Start Shift Checks", f"{start_checks} verified")
    with k3:
        st.metric("End Shift Checks", f"{end_checks} shutdowns")
    with k4:
        st.metric("Pump Transfers", f"{transfers} line changes")
    with k5:
        st.metric("Spills / Issues", f"{spills} flags", delta="Attention Needed" if spills > 0 else "Clear",
                  delta_color="inverse")
    st.markdown("---")

    if not df_audits.empty:
        ac1, ac2, ac3 = st.columns(3)
        for idx, row in df_audits.iterrows():
            target_col = ac1 if (idx % 3 == 0) else (ac2 if idx % 3 == 1 else ac3)
            with target_col:
                with st.container():
                    badge_color = "#EF4444" if row["is_spill"] == "Yes" else "#38BDF8"
                    st.markdown(
                        f"<div style='border:1px solid #334155; border-radius:8px; padding:12px; background-color:#0F172A; margin-bottom:8px;'>"
                        f"<b style='color:{badge_color}; font-size:0.85rem;'>● {row['audit_type']}</b>"
                        f"<span style='float:right; font-size:0.8rem; color:#94A3B8;'>{row['pump_station']}</span><br>",
                        unsafe_allow_html=True)
                    if row["image_filename"]:
                        img_path = os.path.join(UPLOAD_DIR, str(row["image_filename"]))
                        if os.path.exists(img_path):
                            st.image(img_path, use_container_width=True)
                        else:
                            st.caption("🖼️ Image file not found on disk.")
                    else:
                        st.caption("📝 Log entry without image attachment.")
                    st.caption(f"📅 **Time:** `{row['timestamp']}` | 👤 **Operator:** {row['operator_name']}")
                    st.markdown(f"*{row['notes'] if row['notes'] else 'No additional operator notes logged.'}*")
                    st.markdown("</div>", unsafe_allow_html=True)
                    if st.button(f"🗑️ Delete Photo Audit #{row['id']}", key=f"del_gal_aud_{row['id']}",
                                 use_container_width=True):
                        delete_cleanliness_audit(row["id"])
                        st.success(f"Deleted Audit #{row['id']}")
                        st.rerun()
                    st.markdown("<br>", unsafe_allow_html=True)

# ===================== TAB 5: HISTORICAL ANALYTICS =====================
with tab_hist:
    st.markdown("### 📈 Historical Plant Analytics & Production Trends")
    col_f1, col_f2, col_f3 = st.columns(3)
    with col_f1:
        date_range = st.selectbox("📅 Time Horizon", ["Past 7 Days", "Past 30 Days", "Year to Date", "All Time"])
    with col_f2:
        selected_resin = st.selectbox("🧪 Resin Filter", ["All Resins"] + sorted(
            df_logs["resin_type"].dropna().unique().tolist()) if not df_logs.empty else ["All Resins"])
    with col_f3:
        selected_op = st.selectbox("👤 Operator Filter", ["All Operators"] + sorted(
            df_logs["operator_name"].dropna().unique().tolist()) if not df_logs.empty else ["All Operators"])

    today_d = date.today()
    start_date_filter = None

    if date_range == "Past 7 Days":
        start_date_filter = today_d - timedelta(days=7)
    elif date_range == "Past 30 Days":
        start_date_filter = today_d - timedelta(days=30)
    elif date_range == "Year to Date":
        start_date_filter = date(today_d.year, 1, 1)

    hist_df = get_production_logs_df(start_date=start_date_filter, end_date=today_d, resin=selected_resin,
                                     operator=selected_op)

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
            fig_trend = px.line(trend_df, x="date_str", y="bottles_filled", markers=True,
                                title="Units Poured Over Time")
            fig_trend.update_layout(height=320, plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                                    font=dict(color='#94A3B8'))
            st.plotly_chart(fig_trend, use_container_width=True)
        with c2:
            op_df = pour_df.groupby("operator_name")["bottles_filled"].sum().reset_index().sort_values("bottles_filled",
                                                                                                       ascending=False)
            fig_op = px.bar(op_df, x="operator_name", y="bottles_filled", color="operator_name",
                            title="Total Output by Operator")
            fig_op.update_layout(height=320, showlegend=False, plot_bgcolor='rgba(0,0,0,0)',
                                 paper_bgcolor='rgba(0,0,0,0)', font=dict(color='#94A3B8'))
            st.plotly_chart(fig_op, use_container_width=True)

# ===================== TAB CHAT: FLOOR COMMS =====================
with tab_chat:
    st.subheader("💬 Live Floor Communications")
    active_chat_ops = get_operators_with_messages()
    all_ops = active_operators_list
    display_ops = sorted(list(set(active_chat_ops + all_ops)))
    if display_ops:
        chat_col1, chat_col2 = st.columns([1, 3])
        with chat_col1:
            selected_chat_op = st.radio("Operators", display_ops, label_visibility="collapsed",
                                        key="mgr_chat_op_selector")
        with chat_col2:
            if selected_chat_op:
                st.markdown(f"#### Chat with {selected_chat_op}")
                chat_df = get_chat_history_df(selected_chat_op)
                with st.container(height=400):
                    if not chat_df.empty:
                        for _, row in chat_df.iterrows():
                            msg_time = pd.to_datetime(row['timestamp']).tz_localize("UTC").tz_convert(
                                "America/New_York").strftime("%I:%M %p")
                            is_mgr = row['is_manager_reply'] == 1
                            role, avatar = ("user", "👨‍💼") if is_mgr else ("assistant", "👷")
                            with st.chat_message(role, avatar=avatar):
                                st.markdown(
                                    f"**{row['sender_name']}** <span style='font-size:0.7rem; color:#94A3B8;'>{msg_time}</span>",
                                    unsafe_allow_html=True)
                                st.write(row['message'])
                    else:
                        st.info(f"No messages yet with {selected_chat_op}.")
                if prompt := st.chat_input(f"Reply to {selected_chat_op}...", key="mgr_chat_input_box"):
                    send_floor_message(selected_chat_op, "Plant Lead", prompt, is_manager=True)
                    st.rerun()

# ===================== TAB: RESTRICTED ROSTER =====================
with tab_roster:
    st.subheader("👥 Floor Personnel Administration (Manager Access)")
    st.info(
        "💡 **Security Notice:** Managers can provision and manage Floor Personnel. IT Admins manage management accounts and terminations.")

    u_col1, u_col2 = st.columns((1, 2.5))

    with u_col1:
        st.markdown("#### ➕ Provision Floor Personnel")
        with st.form("mgr_create_user_form", clear_on_submit=True):
            new_fullname = st.text_input("Full Name")
            new_email = st.text_input("Work Email")
            new_username = st.text_input("Username / ID")
            new_pin = st.text_input("PIN / Password", type="password")

            # RESTRICTED: Managers can only create Operators or Packers
            new_role = st.selectbox("Role", ("Operator", "Packer"))
            new_shift = st.selectbox("Assigned Shift", ("Shift 1", "Shift 2", "Floater"))
            new_target = st.number_input("Target Rate (L/h)", value=400.0, step=10.0)

            if st.form_submit_button("Create Personnel", type="primary", use_container_width=True):
                if create_user(new_username, new_email, new_pin, new_fullname, new_role.lower(), float(new_target),
                               new_shift):
                    st.success("✅ Account created successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Username or email already exists.")

    with u_col2:
        st.markdown("#### 📋 Floor Roster")
        if not df_users.empty:
            # RESTRICTED: Hide Admins and Managers from the Manager's view
            floor_df = df_users[df_users["role"].isin(["operator", "packer"])]
            if not floor_df.empty:
                st.markdown(
                    f'<div style="overflow-x: auto;">{floor_df[["id", "full_name", "username", "role", "shift"]].to_html(index=False)}</div>',
                    unsafe_allow_html=True)
            else:
                st.caption("No floor personnel found.")

    st.markdown("<br>", unsafe_allow_html=True)

    # RESTRICTED PIN RESET
    with st.expander("🔑 Reset Floor Operator PIN", expanded=False):
        if not df_users.empty:
            floor_df = df_users[df_users["role"].isin(["operator", "packer"])]
            if not floor_df.empty:
                target_user = st.selectbox("Select Personnel", floor_df["username"].tolist(), key="mgr_rst_usr")
                new_temp_pin = st.text_input("New PIN", type="password", key="mgr_rst_pin")
                if st.button("💾 Reset PIN", type="primary"):
                    user_row = floor_df[floor_df["username"] == target_user].iloc[0]
                    update_user_pin(int(user_row["id"]), new_temp_pin)
                    st.success(f"✅ PIN updated for '{target_user}'.")
                    time.sleep(1)
                    st.rerun()
            else:
                st.caption("No floor personnel available for PIN reset.")

# ===================== TAB: GOOGLE SHEETS & CLOUD SYNC =====================
with tab_gsheet:
    st.subheader("☁️ External Reporting & Google Cloud Sync Control Panel")
    st.caption("Configure custom payload types, execution triggers, and metric filters to transmit plant telemetry directly to Google Sheets.")

    col_a, col_b = st.columns(2)
    with col_a:
        export_mode = st.radio(
            "1. Select Data Payload Type",
            ["📊 Aggregated Calculated Metrics (KPI Summary)", "📋 Raw Production Audit Stream"],
            horizontal=False,
            key="mgr_gsheet_payload"
        )
        sync_horizon = st.selectbox(
            "2. Time Horizon Scope",
            ("⚡ Live Today (Active Shift)", "📆 Past 7 Days", "📊 Past 30 Days", "🌐 All Time History")
        )

    with col_b:
        sync_trigger = st.radio(
            "3. Automation Trigger Preference",
            ("👆 Manual On-Demand Push", "📤 Auto-Sync on Shift Handover", "⏱️ Scheduled Background Webhook"),
            horizontal=False,
            key="mgr_gsheet_trigger"
        )

    st.markdown("---")
    st.markdown("#### ⚙️ Payload Column Customization")

    # Generate the dataframe payload based on selections
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
            export_payload_df = pd.DataFrame(columns=[
                "Date", "Shift", "Resin Formulation", "Container Format", "Operator Name",
                "Pump Station", "Units Poured", "Units Packed", "Volume Output (Liters)",
                "Scrap Reject Units", "Quality FPY (%)", "Scrap Rate (%)", "Pending Floor WIP", "Est Skids Built"
            ])
    else:
        if not df_logs.empty:
            export_payload_df = df_logs.drop(columns=[c for c in ["date_obj", "date_str"] if c in df_logs.columns]).copy()
        else:
            export_payload_df = pd.DataFrame(columns=["id", "timestamp", "log_type", "operator_name", "pump_station", "shift", "resin_type", "bottles_filled", "scrap_empty", "scrap_filled", "notes"])

    available_metrics = list(export_payload_df.columns)
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

                    wrapped_payload = {
                        "sheet_name": target_tab,
                        "data": payload
                    }

                    response = requests.post(google_url, json=wrapped_payload)

                    if response.status_code == 200:
                        st.success(f"✅ Dispatched {len(final_df)} records to tab '{target_tab}' in Google Sheets!")
                        st.balloons()
                    else:
                        st.error(f"❌ Transmission Failed ({response.status_code}): {response.text}")
                except Exception as e:
                    st.error(f"❌ Transmission Error: {str(e)}")

# ===================== TAB 10: SHIFT HANDOVER =====================
with tab_handoff:
    st.subheader("📤 Automated Shift Handover & PDF Generation")
    current_settings = get_plant_settings()
    default_list = current_settings.get("handover_emails", "")

    pdf_col1, pdf_col2 = st.columns(2)
    with pdf_col1:
        recipient_emails = st.text_input("Recipient Email Addresses", value=default_list)
    with pdf_col2:
        selected_pdf_theme = st.selectbox(
            "🎨 Select PDF Report Theme / Layout Style:",
            ["Formlabs Forge (Default Dark)", "Executive Clean (Print-Friendly)", "Cyberpunk SCADA (High-Tech)"]
        )

    if st.button("📄 Generate & Dispatch Shift Report", type="primary", use_container_width=True):
        from fpdf import FPDF
        import smtplib
        from email.mime.multipart import MIMEMultipart
        from email.mime.base import MIMEBase
        from email.mime.text import MIMEText
        from email import encoders

        today_str = date.today().strftime("%Y-%m-%d")
        df_today = df_logs[df_logs["date"].astype(str) == today_str] if not df_logs.empty else pd.DataFrame()
        pour_df = df_today[df_today["log_type"] == "Hourly Bottle Count"] if not df_today.empty else pd.DataFrame()
        pack_df = df_today[df_today["log_type"] == "Packing Count"] if not df_today.empty else pd.DataFrame()

        total_poured = int(pour_df["bottles_filled"].sum()) if not pour_df.empty else 0
        total_packed = int(pack_df["bottles_filled"].sum()) if not pack_df.empty else 0
        total_scrap = int(pour_df["scrap_empty"].sum() + pour_df["scrap_filled"].sum()) if not pour_df.empty else 0

        PDF_THEMES = {
            "Formlabs Forge (Default Dark)": {
                "bg_color": (15, 23, 42), "text_color": (248, 250, 252), "sub_color": (148, 163, 184),
                "accent_color": (234, 88, 12), "card_bg": (30, 41, 59), "font": "Arial"
            },
            "Executive Clean (Print-Friendly)": {
                "bg_color": (255, 255, 255), "text_color": (15, 23, 42), "sub_color": (71, 85, 105),
                "accent_color": (2, 132, 199), "card_bg": (241, 245, 249), "font": "Arial"
            },
            "Cyberpunk SCADA (High-Tech)": {
                "bg_color": (9, 1, 23), "text_color": (0, 255, 204), "sub_color": (168, 85, 247),
                "accent_color": (240, 0, 255), "card_bg": (24, 9, 48), "font": "Courier"
            }
        }

        theme = PDF_THEMES[selected_pdf_theme]


        class ThemedPDF(FPDF):
            def __init__(self, theme_cfg):
                super().__init__()
                self.theme = theme_cfg

            def header(self):
                self.set_fill_color(*self.theme["bg_color"])
                self.rect(0, 0, 210, 297, "F")
                self.set_fill_color(*self.theme["accent_color"])
                self.rect(0, 0, 210, 6, "F")


        pdf = ThemedPDF(theme)
        pdf.add_page()
        pdf.set_auto_page_break(auto=True, margin=15)

        pdf.set_font(theme["font"], 'B', 18)
        pdf.set_text_color(*theme["accent_color"])
        pdf.cell(0, 10, txt="FORMLABS PLANT SHIFT HANDOVER", ln=True, align='L')

        pdf.set_font(theme["font"], 'I', 10)
        pdf.set_text_color(*theme["sub_color"])
        pdf.cell(0, 6, txt=f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Theme: {selected_pdf_theme}",
                 ln=True, align='L')
        pdf.ln(10)

        metrics = [
            ("Total Poured", f"{total_poured:,} L"), ("Total Packed", f"{total_packed:,} Units"),
            ("Floor WIP", f"{total_poured - total_packed:,} Pending"), ("Total Scrap", f"{total_scrap:,} Units")
        ]

        pdf.set_font(theme["font"], 'B', 11)
        for i, (label, val) in enumerate(metrics):
            x = 10 if (i % 2 == 0) else 105
            y = pdf.get_y()
            pdf.set_fill_color(*theme["card_bg"])
            pdf.rect(x, y, 90, 22, "F")
            pdf.set_xy(x + 5, y + 3)
            pdf.set_text_color(*theme["sub_color"])
            pdf.cell(80, 5, txt=label.upper(), ln=False)
            pdf.set_xy(x + 5, y + 10)
            pdf.set_text_color(*theme["text_color"])
            pdf.cell(80, 8, txt=val, ln=False)
            if i % 2 == 1: pdf.ln(26)

        pdf_filename = f"Shift_Handover_{today_str}.pdf"
        pdf.output(pdf_filename)
        st.success("✅ Themed PDF Successfully Generated!")

        with open(pdf_filename, "rb") as pdf_file:
            st.download_button("⬇️ Download PDF Report Manually", data=pdf_file, file_name=pdf_filename,
                               mime="application/pdf", use_container_width=True)

        if recipient_emails.strip():
            try:
                sender_email = os.getenv("SENDER_EMAIL") or os.getenv("EMAIL_USER", "")
                sender_password = os.environ.get("EMAIL_PASS")
                msg = MIMEMultipart()
                msg['From'] = sender_email
                msg['To'] = recipient_emails
                msg['Subject'] = f"Formlabs Shift Handover - {today_str}"
                msg.attach(MIMEText(f"Attached is the automated shift handover report for {today_str}.", 'plain'))

                with open(pdf_filename, "rb") as attachment:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(attachment.read())
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f"attachment; filename= {pdf_filename}")
                msg.attach(part)

                server = smtplib.SMTP('smtp.gmail.com', 587)
                server.starttls()
                server.login(sender_email, sender_password)
                server.send_message(msg)
                server.quit()
                st.success(f"📧 Shift Handover Report successfully emailed to: {recipient_emails}")
            except Exception as e:
                st.error(f"Failed to send email: {str(e)}")