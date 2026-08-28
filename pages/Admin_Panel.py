import sys
import os
import time
from datetime import date
import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
import base64

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from database import (
    get_all_users_df, create_user, update_user_role_and_shift, update_user_pin, delete_user_by_username,
    get_plant_settings, update_plant_settings, create_database_backup, restore_database_backup,
    get_production_logs_df, add_hourly_log, BACKUP_DIR, update_user_theme, add_suggestion,
)

st.set_page_config(page_title="IT Admin Console | Formlabs MES", page_icon="🛡️", layout="wide")

try:
    from themes import THEMES
except ImportError:
    THEMES = {
        "Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
st.markdown(THEMES.get(active_theme, THEMES["Default Dark"]), unsafe_allow_html=True)

cookie_manager = stx.CookieManager(key="admin_cookies")

if not st.session_state.get("authenticated", False):
    cached_token = cookie_manager.get(cookie="formlabs_mes_token")
    if cached_token:
        df_users = get_all_users_df()
        user_match = df_users[df_users["username"] == cached_token]
        if not user_match.empty:
            ud = user_match.iloc[0]
            st.session_state.update(
                {"authenticated": True, "user_id": int(ud["id"]), "user_role": ud["role"], "user_name": ud["full_name"],
                 "user_shift": ud.get("shift", "Shift 1"),
                 "preferred_theme": ud.get("preferred_theme", "Default Dark")})
            time.sleep(0.5)
            st.rerun()

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
# --- PERSISTENT AUTO-LOGIN ENGINE & SECURITY GATE ---
import extra_streamlit_components as stx

cookie_manager = stx.CookieManager(key="adm_cookies")

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
with st.sidebar:
    st.markdown("---")
    st.markdown(f"### 🛡️ {st.session_state.get('user_name')}")
    st.caption(f"Role: `IT ADMIN`")

    # --- SYSTEM CHANGELOG ---
    with st.popover("📜 System Changelog", use_container_width=True):
        try:
            with open("CHANGELOG.md", "r", encoding="utf-8") as f:
                st.markdown(f.read())
        except FileNotFoundError:
            st.caption("⚠️ CHANGELOG.md file not found in root directory.")

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown("**🎨 System Theme**")
    current = st.session_state.get("preferred_theme", "Default Dark")

    chosen_theme = st.selectbox(
        "Select Interface Theme",
        list(THEMES.keys()),
        index=list(THEMES.keys()).index(current) if current in THEMES else 0,
        label_visibility="collapsed",
        key="admin_theme_select"
    )
    if chosen_theme != current:
        update_user_theme(st.session_state["user_id"], chosen_theme)
        st.session_state["preferred_theme"] = chosen_theme
        st.rerun()
        # --- UNIVERSAL SUGGESTION & ISSUE BOX ---
        with st.popover("💡 Submit Suggestion / Issue", use_container_width=True):
            st.markdown("#### 💡 Floor Feedback & Issue Reporting")
            st.caption("Noticed a bug, safety concern, or feature idea? Submit it directly to IT & Management.")
            with st.form("sidebar_suggestion_form", clear_on_submit=True):
                sug_category = st.selectbox("Category",
                                            ("Feature Request", "App Bug / Error", "Plant Floor / Safety Issue",
                                             "General Feedback"))
                sug_text = st.text_area("Description / Observation",
                                        placeholder="Describe your idea or the issue you noticed...")
                if st.form_submit_button("🚀 Submit to IT Admin", type="primary", use_container_width=True):
                    if sug_text.strip():
                        from database import add_suggestion

                        add_suggestion(
                            user_name=st.session_state.get("user_name", "Anonymous"),
                            user_role=st.session_state.get("user_role", "operator"),
                            category=sug_category,
                            suggestion=sug_text
                        )
                        st.success("✅ Feedback sent directly to IT Admin!")
                    else:
                        st.warning("⚠️ Please provide a description.")
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("Log Out & Clear Device", type="primary", use_container_width=True):
        cookie_manager.delete("formlabs_mes_token")
        st.session_state.clear()
        time.sleep(0.5)
        st.switch_page("Home.py")

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
                    st.success("✅ Account created successfully!")
                    time.sleep(1)
                    st.rerun()
                else:
                    st.error("❌ Username or email already exists.")

    with u_col2:
        st.markdown("#### 📋 Current Staff Database")
        df_users = get_all_users_df()
        if not df_users.empty:
            st.markdown(
                f'<div style="overflow-x: auto;">{df_users[["id", "full_name", "username", "email", "role", "shift"]].to_html(index=False)}</div>',
                unsafe_allow_html=True)

    with st.expander("🛠️ Modify User Role & Shift Assignment", expanded=False):
        if not df_users.empty:
            modify_user = st.selectbox("Select Personnel", df_users["username"].tolist(), key="mod_user")
            mod_role = st.selectbox("New Role", ("operator", "packer", "manager", "admin"))
            mod_shift = st.selectbox("New Shift", ("Shift 1", "Shift 2", "Shift 3", "Floater"))
            if st.button("💾 Apply Changes", type="primary"):
                user_row = df_users[df_users["username"] == modify_user].iloc[0]
                update_user_role_and_shift(int(user_row["id"]), mod_role, mod_shift)
                st.success(f"✅ Updated '{modify_user}'!")
                time.sleep(1)
                st.rerun()

    with st.expander("🔑 Reset User PIN", expanded=False):
        if not df_users.empty:
            target_user = st.selectbox("Select Personnel", df_users["username"].tolist(), key="rst_usr")
            new_temp_pin = st.text_input("New PIN", type="password")
            if st.button("💾 Reset PIN", type="primary"):
                user_row = df_users[df_users["username"] == target_user].iloc[0]
                update_user_pin(int(user_row["id"]), new_temp_pin)
                st.success(f"✅ PIN updated for '{target_user}'.")
                time.sleep(1)
                st.rerun()

    with st.expander("⚠️ Terminate Account", expanded=False):
        if not df_users.empty:
            user_to_delete = st.selectbox("Select Personnel to Remove", df_users["username"].tolist(), key="del_usr")
            if st.button("🗑️ Delete User", type="primary"):
                if user_to_delete == st.session_state.get("username"):
                    st.error("You cannot delete your own admin account!")
                elif delete_user_by_username(user_to_delete):
                    st.success(f"✅ User '{user_to_delete}' removed.")
                    time.sleep(1)
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
                st.success(f"✅ Cleared {current_wip} units!")
                time.sleep(1)
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
                        st.success(f"✅ Restored from `{selected_backup}`!")
                        time.sleep(1)
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
            st.success("✅ Plant settings updated globally!")
            time.sleep(1)
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
                    st.success(f"✅ Added {new_r_name}!")
                    time.sleep(0.5)
                    st.rerun()

        st.markdown("<br>", unsafe_allow_html=True)
        from database import get_all_reactors_df, delete_reactor

        df_reactors = get_all_reactors_df()

        if not df_reactors.empty:
            for _, r in df_reactors.iterrows():
                with st.container():
                    st.markdown(
                        f"<div style='background:#0F172A; padding:10px; border-radius:6px; border:1px solid #1E293B; margin-bottom:5px;'>"
                        f"<b style='color:#38BDF8;'>{r['reactor_name']}</b> <br>"
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
                    st.success(f"✅ Added {new_p_name}!")
                    time.sleep(0.5)
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
                        f"<span style='color:{status_color}; font-size:0.85rem; font-weight:bold;'>● {p.get('status', 'Active')}</span>"
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
                    st.success("✅ Added code!")
                    time.sleep(0.5)
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
    from database import get_all_suggestions_df, update_suggestion_status, delete_suggestion

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
            with st.container():
                st.markdown(
                    f"""
                    <div style="background:#0D1627; border:1px solid #1E2B45; border-radius:8px; padding:14px; margin-bottom:8px;">
                        <div style="display:flex; justify-content:space-between; align-items:center;">
                            <div>
                                <span style="background:{badge_color}; color:#FFFFFF; font-size:0.75rem; font-weight:800; padding:2px 8px; border-radius:4px;">● {row['status'].upper()}</span>
                                <b style="color:#FFFFFF; font-size:1.05rem; margin-left:8px;">[{row['category']}]</b>
                            </div>
                            <span style="color:#94A3B8; font-size:0.8rem;">👤 <b>{row['user_name']}</b> ({str(row['user_role']).upper()}) | {pd.to_datetime(row['timestamp']).strftime('%Y-%m-%d %H:%M')}</span>
                        </div>
                        <p style="color:#E2E8F0; margin-top:10px; font-size:0.95rem;">{row['suggestion']}</p>
                        {f'<div style="color:#38BDF8; font-size:0.85rem;"><b>Admin Note:</b> {row["admin_notes"]}</div>' if row["admin_notes"] else ''}
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
                            st.success("Updated!")
                            time.sleep(0.5)
                            st.rerun()
                    with btn_col2:
                        if st.button("🗑️", key=f"del_sug_{row['id']}", use_container_width=True):
                            delete_suggestion(row["id"])
                            st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)
    else:
        st.info("No suggestions or issue reports submitted yet.")