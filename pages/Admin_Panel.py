

import os
import sys
import base64
from datetime import datetime, date, timedelta
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import (
    get_all_users_df, create_user, update_user_role_and_shift, update_user_pin, delete_user_by_username,
    unlock_user_account,
    get_plant_settings, update_plant_settings, create_database_backup, restore_database_backup,
    get_production_logs_df, add_hourly_log, BACKUP_DIR, update_user_theme, add_suggestion, do_logout,
    check_authentication
)
from database import esc

st.set_page_config(page_title="IT Admin Console | Formlabs MES", page_icon="🛡️", layout="wide")

st.logo("assets/formlabs_logo.png")


try:
    from themes import THEMES
except ImportError:
    THEMES = {
        "Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
st.markdown(THEMES.get(active_theme, THEMES["Default Dark"]), unsafe_allow_html=True)

cookie_manager = stx.CookieManager(key="admin_cookies")
check_authentication(cookie_manager)

if not st.session_state.get("authenticated", False):
    st.switch_page("Home.py")

if st.session_state.get("user_role") != "admin":
    st.error("🔒 Access Denied: Restricted to IT Administrators.")
    st.stop()


def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except:
        return ""


logo_b64 = get_base64_image("assets/formlabs_logo.png")

with st.sidebar:
    st.markdown("---")
    from database import get_avatar_path
    _avatar_path = get_avatar_path(st.session_state.get("avatar_filename"))
    if _avatar_path:
        _av_col, _name_col = st.columns([1, 4])
        with _av_col:
            st.image(_avatar_path, width=48)
        with _name_col:
            st.markdown(f"### {st.session_state.get('user_name', 'Operator')}")
    else:
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
    st.page_link("pages/Device_Registry.py", label="Device Gateway", icon="🔌")

    st.markdown("---")
    # ---------------------------

    # UNIFIED SETTINGS POPOVER
    with st.popover("⚙️ Account & Preferences", use_container_width=True):
        set_tab1, set_tab2, set_tab3 = st.tabs(["🔑 Security", "🎨 Theme & Avatar", "💡 Feedback"])

        # TAB 1: USERNAME & PIN
        with set_tab1:
            st.markdown("#### Update Account Credentials")
            with st.form("admin_user_cred_form"):
                acc_name = st.text_input("Full Display Name", value=st.session_state.get("user_name", ""))
                acc_user = st.text_input("Username / ID", value=st.session_state.get("username", ""))
                acc_pin = st.text_input("New PIN / Password", type="password", placeholder="Leave blank to keep current PIN")

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
                update_user_theme(st.session_state["user_id"], chosen_t)
                st.session_state["preferred_theme"] = chosen_t
                cookie_manager.set("formlabs_mes_theme", chosen_t, expires_at=datetime.now() + timedelta(days=365))
                st.rerun()

            st.markdown("---")
            st.markdown("#### Profile Picture")
            _current_avatar = get_avatar_path(st.session_state.get("avatar_filename"))
            if _current_avatar:
                st.image(_current_avatar, width=64, caption="Current Avatar")
            new_avatar = st.file_uploader("Upload Avatar", type=["png", "jpg", "jpeg", "webp"], key="set_avatar_upload")
            if st.button("💾 Save Avatar", type="primary", use_container_width=True):
                if new_avatar:
                    from database import update_user_avatar
                    st.session_state["avatar_filename"] = update_user_avatar(st.session_state["user_id"], new_avatar)
                    st.toast("✅ Avatar updated!")
                    st.rerun()

        # TAB 3: FEEDBACK
        with set_tab3:
            st.markdown("#### Universal Feedback Box")
            with st.form("admin_sug_form", clear_on_submit=True):
                s_cat = st.selectbox("Category", ("Feature Request", "App Bug / Error", "Plant Floor Issue", "General Feedback"))
                s_txt = st.text_area("Observation / Description")
                if st.form_submit_button("🚀 Submit Feedback", type="primary", use_container_width=True):
                    if s_txt.strip():
                        add_suggestion(
                            user_name=st.session_state.get("user_name", "Anonymous"),
                            user_role=st.session_state.get("user_role", "admin"),
                            category=s_cat,
                            suggestion=s_txt
                        )
                        st.success("✅ Submitted to IT Admin Inbox!")

    # --- SYSTEM CHANGELOG ---
    with st.popover("📜 System Changelog", use_container_width=True):
        try:
            with open("CHANGELOG.md", "r", encoding="utf-8") as f:
                st.markdown(f.read())
        except FileNotFoundError:
            st.caption("⚠️ CHANGELOG.md file not found in root directory.")

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        do_logout(cookie_manager)
        st.switch_page("Home.py")
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# IT Admins see "God Mode" (All pages accessible)
nav_col1, nav_col2, nav_col3, nav_col4, nav_analytics, nav_admin = st.columns((1.1, 1.1, 1.1, 1.1, 1.1, 1.1))
with nav_col1: st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
with nav_col2: st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
with nav_col3: st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
with nav_col4: st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
with nav_analytics: st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
with nav_admin: st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)

st.markdown("---")

st.markdown(f'''
<div style="display:flex; align-items:center; margin-bottom: 5px;">
    <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain; margin-right: 15px;">
    <h1 style="margin:0; padding:0; font-size: 2.2rem;">🛡️ IT Administrator Console</h1>
</div>
''', unsafe_allow_html=True)

# TAB PILL STYLING
st.markdown(
    """<style>[data-testid="stTabs"] [data-baseweb="tab-highlight"]{display:none !important;} [data-testid="stTabs"] [data-baseweb="tab-list"]{display:flex !important; gap:8px !important; overflow-x:auto !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important;} [data-testid="stTabs"] button[data-baseweb="tab"]{background:rgba(255,255,255,0.05) !important; border:1px solid rgba(255,255,255,0.12) !important; border-radius:20px !important; padding:8px 18px !important; white-space:nowrap !important;} [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]{background:rgba(234,88,12,0.25) !important; border:1px solid #EA580C !important; box-shadow:0 0 12px rgba(234,88,12,0.4) !important;} [data-testid="stTabs"] button[data-baseweb="tab"] p{color:#94A3B8 !important; font-weight:700 !important;} [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] p{color:#FFFFFF !important;}</style>""",
    unsafe_allow_html=True)

tab_roster, tab_sug, tab_db, tab_settings = st.tabs((
    "👥 User Management & Roster",
    "💡 Suggestions & Issue Inbox",
    "📜 System & Database Utilities",
    "⚙️ Plant Configuration"
))

with tab_roster:
    st.subheader("System Access & User Roster")
    u_col1, u_col2 = st.columns((1, 2.5))
    with u_col1:
        st.markdown("#### ➕ Provision New User")
        with st.form("create_user_form", clear_on_submit=True):
            new_fullname = st.text_input("Full Name")
            new_email = st.text_input("Work Email")
            new_username = st.text_input("Username / ID")
            new_pin = st.text_input("PIN / Password", type="password")
            new_role = st.selectbox("Role", ("Operator", "Packer", "Manager", "Admin"))
            new_shift = st.selectbox("Assigned Shift", ("Shift 1", "Shift 2", "Floater"))
            new_target = st.number_input("Target Rate (L/h)", value=400.0, step=10.0)

            if st.form_submit_button("Create Account", type="primary", use_container_width=True):
                if create_user(new_username, new_email, new_pin, new_fullname, new_role.lower(), float(new_target),
                               new_shift):
                    st.toast("✅ Account created successfully!")
                    st.rerun()
                else:
                    st.error("❌ Username or email already exists.")

    with u_col2:
        st.markdown("#### 📋 Current Staff Database")
        df_users = get_all_users_df()
        if not df_users.empty:
            display_df = df_users[["id", "full_name", "username", "email", "role", "shift"]].copy()
            now = datetime.utcnow()
            locked_mask = df_users["locked_until"].apply(
                lambda v: pd.notna(v) and pd.Timestamp(v).to_pydatetime() > now
            )
            display_df["status"] = locked_mask.map({True: "🔒 Locked", False: "✅ Active"})
            st.markdown(
                f'<div style="overflow-x: auto;">{display_df.to_html(index=False)}</div>',
                unsafe_allow_html=True)

            locked_users_df = df_users[locked_mask]
            if not locked_users_df.empty:
                st.warning(f"🔒 {len(locked_users_df)} account(s) currently locked out.")

    with st.expander("🛠️ Modify User Role & Shift Assignment", expanded=False):
        if not df_users.empty:
            modify_user = st.selectbox("Select Personnel", df_users["username"].tolist(), key="mod_user")
            mod_role = st.selectbox("New Role", ("operator", "packer", "manager", "admin"))
            mod_shift = st.selectbox("New Shift", ("Shift 1", "Shift 2", "Shift 3", "Floater"))
            if st.button("💾 Apply Changes", type="primary"):
                user_row = df_users[df_users["username"] == modify_user].iloc[0]
                update_user_role_and_shift(int(user_row["id"]), mod_role, mod_shift)
                st.toast(f"✅ Updated '{modify_user}'!")
                st.rerun()

    with st.expander("🔑 Reset User PIN", expanded=False):
        if not df_users.empty:
            target_user = st.selectbox("Select Personnel", df_users["username"].tolist(), key="rst_usr")
            new_temp_pin = st.text_input("New PIN", type="password")
            if st.button("💾 Reset PIN", type="primary"):
                user_row = df_users[df_users["username"] == target_user].iloc[0]
                update_user_pin(int(user_row["id"]), new_temp_pin)
                st.toast(f"✅ PIN updated for '{target_user}'.")
                st.rerun()

    with st.expander("🔓 Unlock Account", expanded=False):
        if not df_users.empty:
            now = datetime.utcnow()
            locked_mask = df_users["locked_until"].apply(
                lambda v: pd.notna(v) and pd.Timestamp(v).to_pydatetime() > now
            )
            locked_users_df = df_users[locked_mask]
            if locked_users_df.empty:
                st.caption("No accounts are currently locked out.")
            else:
                unlock_target = st.selectbox(
                    "Select Locked Personnel", locked_users_df["username"].tolist(), key="unlock_usr"
                )
                unlock_row = locked_users_df[locked_users_df["username"] == unlock_target].iloc[0]
                locked_until_local = pd.Timestamp(unlock_row["locked_until"]).to_pydatetime()
                minutes_left = max(0, int((locked_until_local - now).total_seconds() // 60) + 1)
                st.caption(f"Locked for {minutes_left} more minute(s), after {int(unlock_row['failed_login_attempts'])} failed attempts.")
                if st.button("🔓 Unlock Now", type="primary"):
                    if unlock_user_account(int(unlock_row["id"])):
                        st.toast(f"✅ '{unlock_target}' unlocked.")
                        st.rerun()

    with st.expander("⚠️ Terminate Account", expanded=False):
        if not df_users.empty:
            user_to_delete = st.selectbox("Select Personnel to Remove", df_users["username"].tolist(), key="del_usr")
            if st.button("🗑️ Delete User", type="primary"):
                if user_to_delete == st.session_state.get("username"):
                    st.error("You cannot delete your own admin account!")
                elif delete_user_by_username(user_to_delete):
                    st.toast(f"✅ User '{user_to_delete}' removed.")
                    st.rerun()

with tab_db:
    st.subheader("Database Management & Utilities")
    with st.expander("🧹 System Utility: Clear Unpacked Floor WIP", expanded=False):
        today_str = date.today().strftime("%Y-%m-%d")
        df_logs = get_production_logs_df()
        df_today = df_logs[df_logs["date"].astype(str) == today_str] if not df_logs.empty else pd.DataFrame()
        sys_poured = int(df_today[df_today["log_type"] == "Hourly Bottle Count"][
                             "bottles_filled"].sum()) if not df_today.empty else 0
        sys_packed = int(
            df_today[df_today["log_type"] == "Packing Count"]["bottles_filled"].sum()) if not df_today.empty else 0
        current_wip = sys_poured - sys_packed

        st.info(f"Current Today's Floor WIP: **{current_wip:,} units**")
        if current_wip > 0:
            if st.button("⚖️ Auto-Pack Remaining WIP to Zero", type="primary"):
                add_hourly_log(operator_name="System Admin", pump_station="Auto-Reconciliation", shift="System",
                               cartridge_type="V2", resin_type="WIP Clear", lot_number=f"WIP-CLR-{today_str}",
                               bottles=current_wip, scrap_empty=0, scrap_filled=0,
                               notes="System auto-generated packing log to clear Floor WIP.", log_type="Packing Count")
                st.toast(f"✅ Cleared {current_wip} units!")
                st.rerun()
        else:
            st.success("Floor WIP is already balanced at 0.")

    st.markdown("#### 🛡️ Database Disaster Recovery")
    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if st.button("📦 Generate Database Backup", type="primary", use_container_width=True):
            filename = create_database_backup()
            if filename:
                st.success(f"✅ Backup created: `{filename}`")
            else:
                st.error("❌ Backup failed. Check pg_dump path.")
    with b_col2:
        if os.path.exists(BACKUP_DIR):
            backup_files = [f for f in os.listdir(BACKUP_DIR) if f.endswith(".sql")]
            if backup_files:
                selected_backup = st.selectbox("Select Backup", sorted(backup_files, reverse=True))
                if st.button("🔄 Restore Database", type="secondary", use_container_width=True):
                    if restore_database_backup(selected_backup):
                        st.toast(f"✅ Restored from `{selected_backup}`!")
                        st.rerun()
                    else:
                        st.error("❌ Restoration failed.")

with tab_settings:
    st.subheader("🏭 Global Plant Operational Parameters")
    st.caption("Update shift schedules, pacing targets, and module availability globally.")

    current_settings = get_plant_settings()

    with st.form("admin_plant_settings_form"):
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("##### ☀️ Shift 1 Schedule")
            s1_start = st.text_input("Start Time (HH:MM)", value=current_settings.get("shift_1_start", "06:00"),
                                     key="s1_start_input")
            s1_hrs = st.number_input("Duration (Hours)", value=float(current_settings.get("shift_1_hours", 8.0)),
                                     step=0.5, key="s1_hrs_input")
            s1_brk = st.number_input("Break Time (Mins)", value=int(current_settings.get("shift_1_break_mins", 60)),
                                     step=15, key="s1_brk_input")
        with c2:
            st.markdown("##### 🌙 Shift 2 Schedule")
            s2_start = st.text_input("Start Time (HH:MM)", value=current_settings.get("shift_2_start", "14:00"),
                                     key="s2_start_input")
            s2_hrs = st.number_input("Duration (Hours)", value=float(current_settings.get("shift_2_hours", 8.0)),
                                     step=0.5, key="s2_hrs_input")
            s2_brk = st.number_input("Break Time (Mins)", value=int(current_settings.get("shift_2_break_mins", 60)),
                                     step=15, key="s2_brk_input")
        with c3:
            st.markdown("##### 🎯 Performance Targets")
            t_lph = st.number_input("Global Target Rate (L/h)", value=float(current_settings.get("target_lph", 400.0)),
                                    step=10.0, key="t_lph_input")
            t_yield = st.number_input("Yield Target (%)", value=float(current_settings.get("yield_target_pct", 99.0)),
                                      step=0.5, key="t_yield_input")
            st.markdown("<br>", unsafe_allow_html=True)
            en_pack = st.checkbox("📦 Enable Packing Module globally",
                                  value=current_settings.get("enable_packing", True), key="en_pack_input")

        st.markdown("##### 📧 Automated Reporting")
        emails = st.text_input("Shift Handover Email Recipients (comma separated)",
                               value=current_settings.get("handover_emails", ""), key="emails_input")

        if st.form_submit_button("💾 Save Operational Parameters", type="primary", use_container_width=True):
            update_dict = {
                "shift_1_start": s1_start, "shift_1_hours": s1_hrs, "shift_1_break_mins": s1_brk,
                "shift_2_start": s2_start, "shift_2_hours": s2_hrs, "shift_2_break_mins": s2_brk,
                "target_lph": t_lph, "yield_target_pct": t_yield, "enable_packing": en_pack,
                "handover_emails": emails
            }
            update_plant_settings(update_dict)
            st.toast("✅ Plant settings updated globally!")
            st.rerun()

    st.markdown("---")
    st.subheader("⚙️ Master Plant Equipment & Configuration")
    st.caption(
        "Add or remove physical assets from the SCADA network. Updates instantly propagate to the Manager Cockpit.")

    col_reactors, col_pumps, col_downtime = st.columns(3)

    # ------------------ 🛢️ REACTOR MANAGEMENT ------------------
    with col_reactors:
        st.markdown("#### 🛢️ Reactor Fleet")
        with st.form("admin_add_reactor_form", clear_on_submit=True):
            new_r_name = st.text_input("Reactor Name", placeholder="e.g. Reactor 5")
            new_r_cap = st.number_input("Max Capacity (Liters)", value=5000, step=500)
            if st.form_submit_button("➕ Add Reactor", type="primary", use_container_width=True):
                if new_r_name.strip():
                    from database import add_reactor

                    add_reactor(new_r_name, new_r_cap)
                    st.toast(f"✅ Added {new_r_name}!")
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        from database import get_all_reactors_df, delete_reactor

        df_reactors = get_all_reactors_df()

        if not df_reactors.empty:
            for _, r in df_reactors.iterrows():
                with st.container():
                    st.markdown(
                        f"<div style='background:#0F172A; padding:10px; border-radius:6px; border:1px solid #1E293B; margin-bottom:5px;'>"
                        f"<b style='color:#38BDF8;'>{esc(r['reactor_name'])}</b> <br>"
                        f"<span style='color:#94A3B8; font-size:0.85rem;'>Capacity: {r['max_capacity_l']:,} L</span>"
                        f"</div>", unsafe_allow_html=True
                    )
                    if st.button("🗑️ Delete", key=f"del_r_{r['id']}", use_container_width=True):
                        delete_reactor(int(r['id']))
                        st.rerun()
                    st.markdown("<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.1);'>",
                                unsafe_allow_html=True)

    # ------------------ 🏷️ PUMP STATION MANAGEMENT ------------------
    with col_pumps:
        st.markdown("#### 🏷️ Pump Stations")
        with st.form("admin_add_pump_form", clear_on_submit=True):
            new_p_name = st.text_input("Station Name", placeholder="e.g. Station A")
            if st.form_submit_button("➕ Add Pump Station", type="primary", use_container_width=True):
                if new_p_name.strip():
                    from database import add_pump_station

                    add_pump_station(new_p_name)
                    st.toast(f"✅ Added {new_p_name}!")
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        from database import get_all_pumps_df, delete_pump_station

        df_pumps = get_all_pumps_df()

        if not df_pumps.empty:
            for _, p in df_pumps.iterrows():
                with st.container():
                    status_color = "#10B981" if p.get('status', 'Active') == "Active" else "#F59E0B"
                    pump_display_name = p.get('station_name', p.get('pump_station', p.get('pump_name', p.get('name',
                                                                                                             'Unknown Station'))))

                    st.markdown(
                        f"<div style='background:#0F172A; padding:10px; border-radius:6px; border:1px solid #1E293B; margin-bottom:5px;'>"
                        f"<b style='color:#FFFFFF;'>{pump_display_name}</b> <br>"
                        f"<span style='color:{status_color}; font-size:0.85rem; font-weight:bold;'>● {esc(p.get('status', 'Active'))}</span>"
                        f"</div>", unsafe_allow_html=True
                    )
                    if st.button("🗑️ Delete", key=f"del_p_{p['id']}", use_container_width=True):
                        delete_pump_station(int(p['id']))
                        st.rerun()
                    st.markdown("<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.1);'>",
                                unsafe_allow_html=True)

    # ------------------ ⚠️ DOWNTIME REASONS MANAGEMENT ------------------
    with col_downtime:
        st.markdown("#### ⚠️ Downtime Codes")
        with st.form("admin_add_dt_form", clear_on_submit=True):
            new_dt_name = st.text_input("Downtime Reason", placeholder="e.g. Missing Materials")
            if st.form_submit_button("➕ Add Reason Code", type="primary", use_container_width=True):
                if new_dt_name.strip():
                    from database import add_downtime_reason

                    add_downtime_reason(new_dt_name)
                    st.toast("✅ Added code!")
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        from database import get_downtime_reasons, delete_downtime_reason

        dt_codes = get_downtime_reasons()

        if dt_codes:
            for code in dt_codes:
                with st.container():
                    st.markdown(
                        f"<div style='background:#0F172A; padding:10px; border-radius:6px; border:1px solid #1E293B; margin-bottom:5px;'>"
                        f"<b style='color:#A855F7;'>{code}</b>"
                        f"</div>", unsafe_allow_html=True
                    )
                    if st.button("🗑️ Delete", key=f"del_dt_{code}", use_container_width=True):
                        delete_downtime_reason(code)
                        st.rerun()
                    st.markdown("<hr style='margin: 8px 0; border-color: rgba(255,255,255,0.1);'>",
                                unsafe_allow_html=True)

with tab_sug:
    st.subheader("💡 Floor Feedback & Issue Inbox")
    from database import get_all_suggestions_df, update_suggestion_status, delete_suggestion, get_avatar_data_uri

    df_sug = get_all_suggestions_df()

    if not df_sug.empty:
        # KPI Counters
        open_cnt = len(df_sug[df_sug["status"] == "Open"])
        review_cnt = len(df_sug[df_sug["status"] == "In Review"])
        impl_cnt = len(df_sug[df_sug["status"] == "Implemented"])

        k1, k2, k3 = st.columns(3)
        k1.metric("Open Feedback", f"{open_cnt} items", delta="Needs Attention" if open_cnt > 0 else "Clear")
        k2.metric("In Review", f"{review_cnt} items")
        k3.metric("Implemented / Resolved", f"{impl_cnt} items")

        st.markdown("---")

        for _, row in df_sug.iterrows():
            badge_color = "#EF4444" if row["status"] == "Open" else ("#F59E0B" if row["status"] == "In Review" else "#10B981")
            # Suggestion has no FK to users (it only ever stored a free-text
            # submitter name), so this avatar is matched by current display
            # name via get_all_suggestions_df's join -- best-effort, same as
            # other legacy name-matched lookups in this app.
            _sug_avatar_uri = get_avatar_data_uri(row.get("avatar_filename"))
            _sug_avatar_html = (
                f'<img src="{_sug_avatar_uri}" style="width:20px; height:20px; border-radius:50%; object-fit:cover; vertical-align:middle; margin-right:2px;">'
                if _sug_avatar_uri else "👤"
            )
            with st.container():
                st.markdown(
                    f"""
                    <div style="background:#0D1627; border:1px solid #1E2B45; border-radius:8px; padding:14px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="background:{badge_color}; color:#FFFFFF; font-size:0.75rem; font-weight:800; padding:2px 8px; border-radius:4px;">● {row['status'].upper()}</span>
                                <b style="color:#FFFFFF; font-size:1.05rem; margin-left:8px;">[{row['category']}]</b>
                            </div>
                            <span style="color:#94A3B8; font-size:0.8rem;">{_sug_avatar_html} <b>{row['user_name']}</b> ({str(row['user_role']).upper()}) | {pd.to_datetime(row['timestamp']).strftime('%Y-%m-%d %H:%M')}</span>
                        </div>
                        <p style="color:#E2E8F0; margin-top:10px; font-size:0.95rem;">{esc(row['suggestion'])}</p>
                        {f'<div style="color:#38BDF8; font-size:0.85rem;"><b>Admin Note:</b> {esc(row["admin_notes"])}</div>' if row["admin_notes"] else ''}
                    </div>
                    """,
                    unsafe_allow_html=True
                )

                col_a, col_b, col_c = st.columns([1.5, 2, 1])
                with col_a:
                    new_st = st.selectbox("Update Status", ("Open", "In Review", "Implemented", "Dismissed"), index=("Open", "In Review", "Implemented", "Dismissed").index(row["status"]), key=f"status_sel_{row['id']}")
                with col_b:
                    a_notes = st.text_input("Resolution / IT Notes", value=row["admin_notes"] or "", key=f"notes_in_{row['id']}")
                with col_c:
                    st.markdown("<br>", unsafe_allow_html=True)
                    btn_col1, btn_col2 = st.columns(2)
                    with btn_col1:
                        if st.button("💾 Save", key=f"save_sug_{row['id']}", use_container_width=True):
                            update_suggestion_status(row["id"], new_st, a_notes)
                            st.toast("Updated!")
                            st.rerun()
                    with btn_col2:
                        if st.button("🗑️", key=f"del_sug_{row['id']}", use_container_width=True):
                            delete_suggestion(row["id"])
                            st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("No suggestions or issue reports submitted yet.")


