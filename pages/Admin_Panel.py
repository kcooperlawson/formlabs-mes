

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
    list_backup_files, prune_old_backups,
    get_production_logs_df, add_hourly_log, BACKUP_DIR, update_user_theme, add_suggestion, do_logout,
    check_authentication, get_assigned_runs_df, role_can_administer, set_cookie
)
from backup_policy import backup_state, DUE_AFTER_HOURS, KEEP_BACKUPS
from database import esc
import crud
from shifts import picker_options as shift_picker_options
import external_links
import shift_clock

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
try:
    from ui_shell import apply_display_preferences
    apply_display_preferences(locals().get('cookie_manager'))
except Exception:
    pass
check_authentication(cookie_manager)

if not st.session_state.get("authenticated", False):
    st.switch_page("Home.py")

_role = st.session_state.get("user_role")
if not role_can_administer(_role):
    st.error("🔒 Access Denied: Restricted to IT Administrators.")
    st.stop()

# A manager standing here is here because the plant runs as a log, and that is
# a decision made in this very panel. Worth saying out loud: the alternative
# is a manager who finds the restore-a-backup button without ever being told
# they had it, and the sentence also explains the one thing that takes the
# access away again.
_here_by_mode = str(_role or "").strip().lower() != "admin"


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

    # In execution mode this is administrators only. In logging mode there is
    # no separate IT role and a manager reaches it too - see
    # crud.can_administer.
    if role_can_administer(st.session_state.get("user_role")):
        st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️")

        # The Device Gateway registry. This link was deliberately absent for a
        # long time: the gateway has never been run against real equipment, and
        # an administrator should not be able to arrive at a configuration
        # screen for hardware nobody has connected. The Plant Settings switch
        # is what changed - the link is back, and it appears only for a plant
        # that has turned the gateway on.
        #
        # Worth keeping in mind here: st.page_link raises on a target it cannot
        # find, and this navigation renders near the top of the page, so one
        # bad line takes the whole console down. The page sweep will not catch
        # it either, because that harness stubs st.page_link out.
        if bool(get_plant_settings().get("enable_device_gateway", 0)):
            st.page_link("pages/Device_Registry.py", label="Device Gateway", icon="🔌")

    from ui_shell import handbook_link
    handbook_link()

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
                set_cookie(cookie_manager, "formlabs_mes_theme", chosen_t, expires_at=datetime.now() + timedelta(days=365))
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
        # switch_page raises to navigate, so an st.rerun() after it never ran.
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
    <h1 style="margin:0; padding:0; font-size: clamp(1.25rem, 4.2vw, 2.2rem); white-space: nowrap;">🛡️ IT Admin Console</h1>
</div>
''', unsafe_allow_html=True)

if _here_by_mode:
    st.info(
        "This plant runs as a **logging system**, so there is no separate IT role and "
        "you have the whole console: accounts and PIN resets, pumps and resins, plant "
        "settings, backups and cleanup. Switching to an execution system, under "
        "**How this plant runs this system** below, hands administration back to "
        "administrator accounts only.")

# TAB PILL STYLING
st.markdown(
    """<style>[data-testid="stTabs"] [data-baseweb="tab-highlight"]{display:none !important;} [data-testid="stTabs"] [data-baseweb="tab-list"]{display:flex !important; gap:8px !important; overflow-x:auto !important; border-bottom: 1px solid rgba(255,255,255,0.1) !important;} [data-testid="stTabs"] button[data-baseweb="tab"]{background:rgba(255,255,255,0.05) !important; border:1px solid rgba(255,255,255,0.12) !important; border-radius:20px !important; padding:8px 18px !important; white-space:nowrap !important;} [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"]{background:rgba(234,88,12,0.25) !important; border:1px solid #EA580C !important; box-shadow:0 0 12px rgba(234,88,12,0.4) !important;} [data-testid="stTabs"] button[data-baseweb="tab"] p{color:#94A3B8 !important; font-weight:700 !important;} [data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] p{color:#FFFFFF !important;}</style>""",
    unsafe_allow_html=True)

tab_roster, tab_sug, tab_crash, tab_db, tab_settings = st.tabs((
    "👥 User Management & Roster",
    "💡 Suggestions & Issue Inbox",
    "🐞 Crash Reports",
    "📜 System & Database Utilities",
    "⚙️ Plant Configuration"
))

with tab_crash:
    # Where a broken screen ends up. Floor terminals are configured not to
    # show tracebacks, which is right, so before this the only trace of a
    # crash was a line in a log file on the plant PC and whether somebody
    # remembered to mention it three days later.
    st.subheader("Crashes the app caught")
    _open = crud.get_error_reports_df(include_resolved=False)
    _all = crud.get_error_reports_df(include_resolved=True)

    if _open.empty:
        st.success("No open crash reports. Nothing has failed since the last one was closed.")
        st.caption(
            "When a page does fail, whoever was on it sees a short reference "
            "code instead of a stack trace, and the fault lands here with the "
            "page, the account, the app version and the real traceback. They "
            "read you the code, you open it."
        )
    else:
        st.caption(
            f"{len(_open)} open. One row per KIND of fault - a page failing on "
            f"every refresh counts up rather than filling the list."
        )
        for _, r in _open.iterrows():
            _seen = r.get("hits", 1)
            _times = "once" if _seen == 1 else f"{_seen} times"
            with st.expander(
                    f"**{r['ref_code']}** · {r.get('error_type') or 'Error'} "
                    f"on {r.get('page') or 'unknown page'} · seen {_times}"):
                cc1, cc2 = st.columns(2)
                cc1.markdown(f"**First seen:** {r.get('occurred_at')}")
                cc2.markdown(f"**Last seen:** {r.get('last_seen_at')}")
                cc1.markdown(f"**Who was on it:** {r.get('user_name') or '—'} "
                             f"({r.get('user_role') or '—'})")
                cc2.markdown(f"**App version:** {r.get('app_version') or '—'}")
                st.markdown(f"**Message:** {r.get('message') or '—'}")
                st.code(r.get("traceback") or "No traceback recorded.",
                        language="python")
                _note = st.text_input("Note (optional)", key=f"crashnote_{r['id']}")
                if st.button("Mark resolved", key=f"crashfix_{r['id']}",
                             use_container_width=True):
                    if crud.resolve_error_report(
                            int(r["id"]),
                            resolved_by=st.session_state.get("user_name", ""),
                            note=_note):
                        st.rerun()
                    else:
                        st.error("Could not close that one.")

    _closed = 0 if _all.empty else int((_all["resolved"] == 1).sum())
    if _closed:
        # Closed ones are kept rather than deleted: a fault that comes back
        # after being closed is a more interesting fact than one nobody ever
        # looked at, and it only reads as "came back" if the first one is
        # still there.
        with st.expander(f"Closed ({_closed})"):
            st.dataframe(
                _all[_all["resolved"] == 1][
                    ["ref_code", "page", "error_type", "hits",
                     "last_seen_at", "resolved_by", "note"]],
                use_container_width=True, hide_index=True)

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
            _mod_current = str(df_users[df_users["username"] == modify_user]["shift"].iloc[0]) \
                if "shift" in df_users.columns else ""
            mod_shift = st.selectbox("New Shift",
                                     shift_picker_options(get_plant_settings(), _mod_current))
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

    # The state of the automatic backup, said out loud. A backup section that
    # only offers a button tells a manager nothing about whether the plant is
    # actually protected, and "no news" is exactly what a stalled backup looks
    # like. See backup_policy.
    _state = backup_state(list_backup_files())
    if _state["state"] == "ok":
        st.success(f"🟢 Automatic backup is running. {_state['message']}")
    elif _state["state"] == "stale":
        st.warning(f"🟠 {_state['message']} Take one now, and check there is "
                   f"disk space and that pg_dump is still on this machine.")
    else:
        st.error(f"🔴 {_state['message']} Take one now.")
    st.caption(f"One is taken automatically when the newest is more than "
               f"{int(DUE_AFTER_HOURS)} hours old and somebody opens the app; "
               f"the {KEEP_BACKUPS} most recent are kept and older ones removed.")

    b_col1, b_col2 = st.columns(2)
    with b_col1:
        if st.button("📦 Generate Database Backup", type="primary", use_container_width=True):
            filename = create_database_backup()
            if filename:
                prune_old_backups()
                st.success(f"✅ Backup created: `{filename}`")
                st.rerun()
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
            # The app was written assuming three shifts; this plant runs two.
            # A number here rather than a constant in source, because adding a
            # shift is an operational decision, not a code change.
            s_count = st.number_input("Shifts run per day", min_value=1, max_value=3,
                                      value=int(current_settings.get("shift_count", 2)),
                                      step=1, key="shift_count_input",
                                      help="Existing logs on a shift you stop running keep their "
                                           "label and stay in every report - the pickers just stop "
                                           "offering it for new entries.")
            t_lph = st.number_input("Global Target Rate (L/h)", value=float(current_settings.get("target_lph", 400.0)),
                                    step=10.0, key="t_lph_input")
            t_yield = st.number_input("Yield Target (%)", value=float(current_settings.get("yield_target_pct", 99.0)),
                                      step=0.5, key="t_yield_input")
            st.markdown("<br>", unsafe_allow_html=True)
            en_pack = st.checkbox("📦 Enable Packing Module globally",
                                  value=current_settings.get("enable_packing", True), key="en_pack_input")
            # Off unless a plant actually decants. When it is off the operator's
            # Container Format list holds exactly the four entries it always
            # has, which is the point of it being a setting rather than a
            # feature everybody has to scroll past.
            en_bulk = st.checkbox("🛢️ Allow bulk pours (drum, tote, pail)",
                                  value=current_settings.get("enable_bulk_pour", False),
                                  key="en_bulk_input",
                                  help="Adds a 'Bulk / Drum' container format that takes a "
                                       "measured amount in litres or kilograms instead of a "
                                       "container count, on the operator's form and on the "
                                       "reactor page. Leave off if everything here is poured "
                                       "into cartridges and jugs.")

            # The machine gateway. It has been built since August and has never
            # been connected to real equipment here, so the page that
            # configures it was unlinked - findable only by typing its address.
            # That is not the same as optional: it meant a plant that DID want
            # to wire a bench scale in had no way to find the screen, or to
            # know it existed. Off by default, and when it is on the registry
            # appears in the manager's console.
            en_gateway = st.checkbox("🔌 Machine gateway (bench scales, pump controllers)",
                                     value=current_settings.get("enable_device_gateway", False),
                                     key="en_gateway_input",
                                     help="Puts the Device Gateway registry in the Manager "
                                          "Cockpit, for registering equipment and mapping what "
                                          "it reports. Readings written by a machine go through "
                                          "the same path an operator's typed entry does, so "
                                          "every figure in the app already understands them. "
                                          "Nothing on the floor changes until a device is "
                                          "actually registered.")



        # Full width, outside the three columns: seven checkboxes squeezed into a
        # third of the width wrapped their labels one letter per line, which is a
        # worse way of saying "Mon" than not saying it.
        #
        # This is what stops the stopped-record alarm going off every Saturday on
        # a plant that does not work weekends. The shift clock only ever knew what
        # time it was, never what day, so every day looked like a working day and
        # the wall display raised an alarm about a weekend - and an alarm that
        # cries wolf every weekend is one nobody reads by Monday.
        st.markdown("---")
        st.markdown("**📅 Days this plant runs**")
        st.caption("Shifts only count as running on these days, so the stopped-record alarm "
                   "stays quiet on a weekend or a shutdown day instead of reporting an empty "
                   "log as a fault. A shift counts by the day it STARTS, so a Friday night "
                   "shift is still watched into Saturday morning.")
        _saved_days = shift_clock.parse_operating_days(current_settings.get("operating_days"))
        # Saved, not picked: these are inside a form, so their values do not reach
        # Python until Save is pressed. A line claiming to describe the current
        # selection would be describing the previous one.
        st.caption(f"Saved: **{shift_clock.describe_operating_days(current_settings.get('operating_days'))}** "
                   "— change the boxes and press Save Operational Parameters.")
        _day_cols = st.columns(7)
        _picked = set()
        for _i, _lbl in enumerate(shift_clock.DAY_LABELS):
            with _day_cols[_i]:
                if st.checkbox(_lbl, value=_i in _saved_days, key=f"op_day_{_i}"):
                    _picked.add(_i)
        op_days = shift_clock.format_operating_days(_picked)

        # ------------------ HOW MUCH OF THE APP THIS PLANT USES ------------------
        # The application grew work orders and a separate IT role first, so
        # every screen assumed a manager had dispatched a run and somebody else
        # administered the thing. A plant that wants the log and one person in
        # charge of it had no way to say so, and got told it was misconfigured
        # on every screen instead.
        #
        # One picker rather than two switches, because the two go together in
        # practice: a plant small enough not to dispatch work is a plant small
        # enough not to have an IT person, and one sentence is easier to
        # explain to the person deciding than two.
        st.markdown("##### 🏭 How this plant runs this system")
        simple_now = bool(current_settings.get("simple_mode", True))
        MODE_LOG = "Logging system"
        MODE_MES = "Execution system"
        mode = st.radio(
            "Mode", (MODE_LOG, MODE_MES),
            index=0 if simple_now else 1,
            key="plant_mode_input", label_visibility="collapsed",
            captions=(
                "Operators log; managers read the record and run the system. No work "
                "orders, and no separate IT role — a manager reaches this console.",
                "Work orders dispatched to stations and tracked against a target, and "
                "administration separated from the manager role again.",
            ),
            help="Nothing is deleted either way. Runs already entered stay in the "
                 "database and reappear the moment this is set back.")
        use_orders = (mode == MODE_MES)

        # The form behind the QR sticker on the pump. A setting rather than a
        # constant because this application does not own that form - whoever
        # does can move it, and moving it should cost one field here.
        st.markdown("##### 🔗 Pump Form Link")
        st.caption(
            "Puts a button on the operator terminal that opens this address in a new tab. "
            "The MES stays open behind it, so an operator can fill the form in and come back "
            "mid-log without signing in again. Leave it empty and no button appears."
        )
        pf_c1, pf_c2 = st.columns((3, 2))
        with pf_c1:
            pump_url = st.text_input("Address", value=current_settings.get("pump_form_url", ""),
                                     placeholder="https://forms.example.com/pump-check",
                                     key="pump_form_url_input")
        with pf_c2:
            pump_label = st.text_input("Button wording",
                                       value=current_settings.get("pump_form_label", ""),
                                       placeholder="Open the pump form",
                                       key="pump_form_label_input")

        if st.form_submit_button("💾 Save Operational Parameters", type="primary", use_container_width=True):
            # Checked here, on the screen of the person who can fix it, rather
            # than on the operator terminal where a bad address becomes a
            # button that goes nowhere. Stored normalised, so the operator page
            # never has to cope with a missing scheme or a trailing full stop.
            pump_clean, pump_problem = external_links.normalise(pump_url)

            # Switching to an execution system takes administration away from
            # managers. In a plant that has been running as a log there may be
            # no administrator account at all - the mode was what granted the
            # access - and saving that would leave nobody able to reach this
            # console, including to switch it back. Refuse the mode change,
            # save everything else, and say what has to exist first.
            st.session_state.pop("_no_admin_warning", None)
            mode_blocked = False
            if simple_now and use_orders:
                try:
                    _users = get_all_users_df()
                    _admins = 0 if _users.empty else int(
                        (_users["role"].astype(str).str.strip().str.lower() == "admin").sum())
                except Exception:
                    _admins = 1          # cannot tell: do not block on a bad read
                if _admins == 0:
                    mode_blocked = True
                    st.session_state["_no_admin_warning"] = (
                        "This plant has no administrator account, and an execution "
                        "system restricts this console to administrators — saving that "
                        "would lock everyone out of it, including you. Give somebody "
                        "the Administrator role under Personnel below, then set the "
                        "mode again. Every other setting on this form was saved.")

            update_dict = {
                "shift_1_start": s1_start, "shift_1_hours": s1_hrs, "shift_1_break_mins": s1_brk,
                "shift_2_start": s2_start, "shift_2_hours": s2_hrs, "shift_2_break_mins": s2_brk,
                "shift_count": int(s_count),
                "target_lph": t_lph, "yield_target_pct": t_yield, "enable_packing": en_pack,
                "enable_bulk_pour": en_bulk,
                "enable_device_gateway": en_gateway,
                "operating_days": op_days,
                # Stored as the negative of the picker: the column is named for
                # the smaller configuration, so the default value of a row
                # nobody has touched is the smaller one.
                "simple_mode": simple_now if mode_blocked else (not use_orders),
                "pump_form_url": pump_clean,
                "pump_form_label": (pump_label or "").strip()[:60],
            }
            update_plant_settings(update_dict)

            # Switching work orders off while runs are still open hides them
            # from the operators standing at those stations, and takes the lot
            # check's expected value with them - it stops comparing and starts
            # recording. A legitimate thing to want; not a thing to find out
            # about a shift later. Checked after the save rather than beside
            # the checkbox because a widget inside a form does not rerun the
            # page, so a notice there would describe the previous state.
            st.session_state.pop("_orders_off_warning", None)
            if simple_now is False and use_orders is False:
                try:
                    _runs = get_assigned_runs_df()
                    _live = 0 if _runs.empty else int(
                        _runs["status"].isin(["Active", "Pouring", "Queued"]).sum())
                except Exception:
                    _live = 0
                if _live:
                    st.session_state["_orders_off_warning"] = (
                        f"{_live} run{'s are' if _live != 1 else ' is'} still open. "
                        "They are hidden from the operator terminal now, and the lot "
                        "check records what was poured instead of comparing it against "
                        "an expected lot. Nothing was deleted — set the mode back to "
                        "bring them back.")

            if pump_problem:
                # Everything else saved; say plainly which part did not, rather
                # than a success toast over a setting that quietly did nothing.
                st.session_state["_pump_form_warning"] = (
                    f"{pump_problem} That address was not saved, so no button will "
                    "appear on the operator terminal.")
            else:
                st.session_state.pop("_pump_form_warning", None)
            st.toast("✅ Plant settings updated globally!")
            st.rerun()

    if st.session_state.get("_pump_form_warning"):
        st.warning("⚠️ " + st.session_state["_pump_form_warning"])

    if st.session_state.get("_orders_off_warning"):
        st.warning("⚠️ " + st.session_state["_orders_off_warning"])

    if st.session_state.get("_no_admin_warning"):
        st.error("🔒 " + st.session_state["_no_admin_warning"])

    st.markdown("---")
    st.subheader("⚙️ Master Plant Equipment & Configuration")
    st.caption(
        "Add or remove physical assets from the SCADA network. Updates instantly propagate to the Manager Cockpit.")

    col_reactors, col_pumps, col_downtime = st.columns(3)

    # ------------------ 🛢️ REACTOR MANAGEMENT ------------------
    with col_reactors:
        st.markdown("#### 🛢️ Reactor Fleet")
        # The pump and the resin are on this form for a reason. A vessel's
        # level is worked out from the logs that match its pump and its resin,
        # and until now this form captured neither - so a tank added here was
        # never linked to anything, never registered a pour, and read full for
        # ever. Both can be changed later on the Live Reactors page.
        _pumps_for_r = ["— not set yet —"] + [str(x) for x in crud.get_active_pumps()]
        _specs_for_r = crud.get_all_resin_specs_df()
        _resins_for_r = ["— not set yet —"] + (
            sorted(_specs_for_r["resin_name"].dropna().astype(str).unique().tolist())
            if not _specs_for_r.empty else [])
        with st.form("admin_add_reactor_form", clear_on_submit=True):
            new_r_name = st.text_input("Reactor Name", placeholder="e.g. Reactor 5")
            new_r_cap = st.number_input("Max Capacity (Liters)", value=5000, step=500)
            new_r_pump = st.selectbox("Feeds which pump station?", _pumps_for_r)
            new_r_resin = st.selectbox("Resin currently in it", _resins_for_r)
            new_r_tag = st.text_input("Asset tag", placeholder="e.g. M-205")
            new_r_bay = st.text_input("Bay marker", placeholder="e.g. E2", max_chars=2)
            st.caption("The pump and the resin are what tell the app a pour came out of "
                       "**this** tank. Leave them unset and the level will not move.")
            if st.form_submit_button("➕ Add Reactor", type="primary", use_container_width=True):
                if new_r_name.strip():
                    from database import add_reactor

                    add_reactor(
                        new_r_name, new_r_cap,
                        asset_tag=new_r_tag,
                        bay_marker=new_r_bay,
                        assigned_pump="" if new_r_pump.startswith("—") else new_r_pump,
                        current_resin="" if new_r_resin.startswith("—") else new_r_resin)
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


