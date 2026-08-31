
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

# --- NEW IMPORTS FOR ANIMATION ---
# st_lottie is the actual render function this page calls (see the
# "Mark Done" button below) — `import streamlit_lottie` alone only binds
# the module name, not st_lottie itself, which is what was crashing every
# "Mark Done" click with NameError: name 'st_lottie' is not defined.
from streamlit_lottie import st_lottie
import requests

from database import (
    add_hourly_log,
    add_lot_verification,
    save_lot_photo,
    is_placeholder_lot,
    lots_match,
    add_downtime_log,
    add_cleanliness_audit,
    get_assigned_runs_df,
    update_assigned_run_progress,
    update_run_status,
    get_all_resin_specs_df,
    get_active_pumps,
    get_downtime_reasons,
    get_active_operators,
    get_production_logs_df,
    get_all_reactors_df,
    reconcile_reactor_level,
    reconcile_reactor_liters,
    has_completed_daily_checklist,
    submit_daily_checklist,
    update_user_role_and_shift,
    get_chat_history_df,
    send_floor_message,
    get_plant_settings,
    add_suggestion,
    do_logout,
    check_authentication,
)
from database import esc
import base64

import extra_streamlit_components as stx
cookie_manager = stx.CookieManager(key="op_cookies")

# Load the Lottie Animation once
def load_lottieurl(url):
    """Fetch the run-complete animation without ever taking the page down.

    This runs while the page script is still loading, so an unguarded
    requests.get here is a single point of failure for the whole operator
    terminal: a slow CDN, a proxy, or a plant PC that has lost its internet
    would hang the page and then raise before one widget rendered. The
    animation is decoration; the terminal is not. Every caller already
    checks `if lottie_success:` before rendering, so None is safe.
    """
    try:
        r = requests.get(url, timeout=3)
        return r.json() if r.status_code == 200 else None
    except Exception:
        return None

# Fetched once per session rather than on every rerun - Streamlit re-executes
# this script top to bottom on every widget interaction, and an operator
# should not be waiting on a CDN round trip each time they touch a number.
if "lottie_success" not in st.session_state:
    st.session_state["lottie_success"] = load_lottieurl(
        "https://assets10.lottiefiles.com/packages/lf20_lk80fpsm.json")
lottie_success = st.session_state["lottie_success"]

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""

logo_b64 = get_base64_image("assets/formlabs_logo.png")

st.set_page_config(page_title="Operator Terminal | Formlabs MES", page_icon="📝", layout="wide")


st.logo("assets/formlabs_logo.png")

# ===================== DYNAMIC THEME INJECTION =====================
try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
if active_theme not in THEMES:
    active_theme = "Default Dark"

st.markdown(THEMES[active_theme], unsafe_allow_html=True)
# ===================================================================

st.markdown(f"""
<div style="display:flex; align-items:center; margin-bottom: 5px;">
    <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain; margin-right: 15px;">
    <h1 style="margin:0; padding:0; font-size: 2.2rem;">📝 Formlabs Operator Workstation Terminal</h1>
</div>
""", unsafe_allow_html=True)

# --- PERSISTENT AUTO-LOGIN ENGINE & SECURITY GATE ---
check_authentication(cookie_manager)

if not st.session_state.get("authenticated", False):
    st.switch_page("Home.py")

# 1. Initialize User & Role FIRST
current_user = st.session_state.get("user_name") or "Keagan C."

# 1. Initialize User & Role FIRST
current_user = st.session_state.get("user_name") or "Keagan C."
current_role = st.session_state.get("user_role") or "operator"
current_shift = st.session_state.get("user_shift") or "Shift 1"

# ===================== ROLE-BASED TOP NAVIGATION =====================
current_role = st.session_state.get("user_role", "operator")

st.markdown("<br>", unsafe_allow_html=True)
if current_role == "admin":
    # God Mode (Now 6 Columns)
    nav_1, nav_2, nav_3, nav_4, nav_5, nav_6 = st.columns(6, gap="small")
    with nav_1:
        st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2:
        st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3:
        st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4:
        st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5:
        st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
    with nav_6:
        st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)
elif current_role == "manager":
    # Manager Suite (Now 5 Columns)
    nav_1, nav_2, nav_3, nav_4, nav_5 = st.columns(5, gap="small")
    with nav_1:
        st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2:
        st.page_link("pages/Operator_Form.py", label="Operator", icon="📝", use_container_width=True)
    with nav_3:
        st.page_link("pages/Manager_Cockpit.py", label="Manager", icon="📊", use_container_width=True)
    with nav_4:
        st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)
    with nav_5:
        st.page_link("pages/Analytics_Hub.py", label="Analytics", icon="🌌", use_container_width=True)
else:
    # Operator View (Stays 3 Columns)
    nav_1, nav_2, nav_3 = st.columns(3, gap="small")
    with nav_1:
        st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    with nav_2:
        st.page_link("pages/Operator_Form.py", label="Workstation", icon="📝", use_container_width=True)
    with nav_3:
        st.page_link("pages/Live_Reactors.py", label="Reactors", icon="🛢️", use_container_width=True)

st.markdown("---")

# ===================== SIDEBAR: PROFILE & SETTINGS =====================
# ===================== SIDEBAR: PROFILE & SETTINGS =====================
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

    # --- CUSTOM ROUTER MENU ---
    st.markdown("#### 🗺️ Navigation")
    st.page_link("Home.py", label="Live SCADA", icon="⚡", use_container_width=True)
    st.page_link("pages/Operator_Form.py", label="Workstation", icon="📝", use_container_width=True)
    st.page_link("pages/Live_Reactors.py", label="Live Reactors", icon="🛢️", use_container_width=True)

    # Only show Manager and Analytics to Managers/Admins
    if st.session_state.get("user_role") in ["manager", "admin"]:
        st.page_link("pages/Manager_Cockpit.py", label="Manager Cockpit", icon="📊", use_container_width=True)
        st.page_link("pages/Analytics_Hub.py", label="Analytics Hub", icon="🌌", use_container_width=True)

    # Only show IT Admin to Admins
    if st.session_state.get("user_role") == "admin":
        st.page_link("pages/Admin_Panel.py", label="IT Admin", icon="🛡️", use_container_width=True)

    st.markdown("---")
    # --------------------------

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
                        st.toast(f"✅ {msg}")
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
                        st.toast("✅ Submitted to IT Admin!")

    st.markdown("<br>", unsafe_allow_html=True)

    # --- LAUNCH TV MODE ---
    if current_role in ["admin", "manager"]:
        st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        do_logout(cookie_manager)
        st.switch_page("Home.py")
        st.rerun()


# ===================== MANAGER & ADMIN DEBUG / IMPERSONATION MODE =====================
if current_role in ["manager", "admin"]:
    st.markdown("""
    <div style='background-color: rgba(245, 158, 11, 0.1); border: 1px solid #F59E0B; border-radius: 8px; padding: 12px; margin-bottom: 16px;'>
        <b style='color: #F59E0B;'>🛠️ Superuser Debug Mode Active</b><br>
        <span style='color: #E2E8F0; font-size: 0.85rem;'>Signed in as Management/Admin. Select an operator below to view their active runs and submit logs for system testing.</span>
    </div>
    """, unsafe_allow_html=True)

    op_list = get_active_operators()
    if current_user not in op_list:
        op_list.insert(0, current_user)

    current_user = st.selectbox("Impersonate Operator for Testing:", op_list)
else:
    st.caption(f"Logged in as: **{current_user}** ({current_role.upper()}) | Live Machine Sync Active")

# ===================== LOT MASKING =====================
# Blind entry only works if the answer isn't already on the screen. The
# active-run card sits directly above the verification gate, so for the
# roles the gate applies to it shows a mask instead of the run's lot.
# Managers and admins still see the real value - they're the ones who have
# to compare it against what an operator typed.
def _display_lot(lot_value, cartridge_type=None):
    lot = str(lot_value or "N/A")
    if str(st.session_state.get("user_role", "operator")) in ("manager", "admin"):
        return lot
    if str(cartridge_type or "").strip().upper() == "RPS":
        return lot          # RPS carries no label, so there is nothing to blind
    return "•" * 9 if lot not in ("", "N/A", "None") else lot


# ===================== PERSONALIZED TODAY'S STATS =====================
df_logs = get_production_logs_df()
today_str = date.today().strftime("%Y-%m-%d")

if not df_logs.empty:
    df_logs["date_str"] = pd.to_datetime(df_logs["date"]).dt.strftime("%Y-%m-%d")
    df_today = df_logs[df_logs["date_str"] == today_str]
else:
    df_today = pd.DataFrame()

if current_role != "manager" and not df_today.empty:
    df_today = df_today[df_today["operator_name"] == current_user]

poured_df = df_today[df_today["log_type"] == "Hourly Bottle Count"] if not df_today.empty else pd.DataFrame()
packed_df = df_today[df_today["log_type"] == "Packing Count"] if not df_today.empty else pd.DataFrame()

poured_units = int(poured_df["bottles_filled"].sum()) if not poured_df.empty else 0
packed_units = int(packed_df["bottles_filled"].sum()) if not packed_df.empty else 0
scrap_units = int(poured_df["scrap_empty"].sum() + poured_df["scrap_filled"].sum()) if not poured_df.empty else 0

st.markdown(f"### 📊 Today's Performance: {current_user if current_role != 'manager' else 'Plant-Wide'}")

if current_role == "operator":
    c1, c2, c3 = st.columns(3)
    c1.metric("🧪 Units Poured", f"{poured_units:,}")
    c2.metric("🗑️ Scrap Units", f"{scrap_units:,}")
    c3.metric("✅ Quality Yield", f"{(poured_units / (poured_units + scrap_units) * 100):.1f}%" if (poured_units + scrap_units) > 0 else "100.0%")
elif current_role == "packer":
    c1, c2 = st.columns(2)
    c1.metric("📦 Units Packed", f"{packed_units:,}")
    c2.metric("⏳ Shift Status", "On Track")
elif current_role == "manager":
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("🧪 Plant Units Poured", f"{poured_units:,}")
    c2.metric("📦 Plant Units Packed", f"{packed_units:,}")
    c3.metric("⏳ Floor WIP (Unpacked)", f"{poured_units - packed_units:,}", delta="Pending Pack-Out", delta_color="off")
    c4.metric("✅ Quality Yield", f"{(poured_units / (poured_units + scrap_units) * 100):.1f}%" if (poured_units + scrap_units) > 0 else "100.0%")

st.markdown("---")

# ===================== THE HARD GATE: DAILY STARTUP CHECKLIST =====================
# Only enforce this for Operators and Packers, not Managers in Debug mode
if current_role in ["operator", "packer"]:
    # Which station the operator is standing at is part of the question. A
    # checklist certifies the condition of one pump - bins staged, station
    # clean - so someone moved to a different pump has certified nothing
    # about it and gets asked again. The selector below writes to the same
    # session_state key ("h_pump") the Hourly Pouring tab uses, so the pump
    # chosen here is the pump they end up logging against; there is only
    # ever one answer to "which station am I at".
    if current_role == "packer":
        _checklist_pumps = []
        checklist_station = "Pack-Out Station"
    else:
        _checklist_pumps = get_active_pumps() or ["New Pump #1"]
        if st.session_state.get("h_pump") not in _checklist_pumps:
            _saved_station = cookie_manager.get(f"op_station_{current_user.replace(' ', '')}")
            st.session_state["h_pump"] = (_saved_station if _saved_station in _checklist_pumps
                                          else _checklist_pumps[0])
        checklist_station = st.session_state["h_pump"]

    if not has_completed_daily_checklist(current_user, current_shift, checklist_station):
        st.error("🛑 **TERMINAL LOCKED: PRE-SHIFT VALIDATION REQUIRED**")
        st.info(
            f"Welcome, {current_user}. Complete the startup checklist for **{checklist_station}** "
            f"on **{current_shift}** before the production modules unlock.")

        if current_role != "packer":
            st.selectbox(
                "📍 Which pump station are you starting at?", _checklist_pumps, key="h_pump",
                help="Changing this switches which station's checklist you're completing — and "
                     "carries through to your logging tab, so you only answer it once.")

        # --- Cookie check to survive page refreshes ---
        # Keyed by station as well as operator: moving to a new pump means a
        # new cleanliness photo of THAT pump, not a pass carried over from the
        # one they left.
        clean_cookie_name = f"clean_chk_{current_user.replace(' ', '')}_{checklist_station.replace(' ', '')}"
        clean_flag_key = f"pre_shift_clean_done_{checklist_station.replace(' ', '')}"

        # If the cookie has today's date, they already submitted the photo!
        if cookie_manager.get(clean_cookie_name) == str(date.today()):
            st.session_state[clean_flag_key] = True
        elif clean_flag_key not in st.session_state:
            st.session_state[clean_flag_key] = False

        st.markdown("### 📋 Daily Startup Checklist")

        # --- STEP 1: THE AUTO-CHECK (CLEANLINESS AUDIT) ---
        if not st.session_state[clean_flag_key]:
            with st.expander("📸 Step 1: Perform & Submit Morning Cleanliness Check", expanded=True):
                st.caption("Submit your start-of-shift photo audit here to satisfy this requirement.")

                audit_station = checklist_station
                st.caption(f"Station: **{audit_station}** — set by the picker above.")
                audit_notes = st.text_area("Observations", placeholder="Station clean, ready for shift.",
                                           key="pre_notes")

                photo_method = st.radio("Photo Input Method", ("Take Live Camera Photo", "Upload Image File"),
                                        horizontal=True, key="pre_photo_rad")
                up_photo = None

                if photo_method == "Upload Image File":
                    up_photo = st.file_uploader("Upload station photo", type=["png", "jpg", "jpeg", "webp"],
                                                key="pre_upload")
                else:
                    up_photo = st.camera_input("Capture live photo", key="pre_cam")

                if st.button("💾 Submit Cleanliness Report", type="primary", use_container_width=True):
                    if up_photo is not None:
                        add_cleanliness_audit(
                            audit_type="Start Of Shift (Cleanliness Check)",
                            operator_name=current_user,
                            pump_station=audit_station,
                            shift=current_shift,
                            resin_type="",
                            notes=audit_notes,
                            is_spill=False,
                            uploaded_file=up_photo
                        )
                        # Flip the flag and save the cookie for today!
                        from datetime import timedelta

                        st.session_state[clean_flag_key] = True
                        cookie_manager.set(clean_cookie_name, str(date.today()),
                                           expires_at=datetime.now() + timedelta(hours=12))

                        st.toast("✅ Cleanliness Audit successfully recorded!")
                        st.rerun()
                    else:
                        st.warning("⚠️ A photo is required for the pre-shift audit.")
        else:
            # The Auto-Check Success State!
            st.toast("✅ **Step 1: Morning Cleanliness Check — LOGGED & COMPLETED**")

        # --- STEP 2: MANUAL CHECKS & FINAL UNLOCK ---
        with st.form("startup_checklist_form"):
            st.markdown("#### Step 2: Final Verification")

            # 1. Universal QR Check
            qr_check = st.checkbox("📱 I have scanned the daily station QR Code and submitted the external checksheet.")

            # 2. Dynamic Material Check based on Role
            if current_role == "packer":
                mat_text = "📦 I have verified all labels, boxes, and necessary materials are staged for my pack-out run."
            else:
                mat_text = "🛒 I have verified all bins of empty cartridges and receiving carts for filled bottles are staged for my run."

            mat_check = st.checkbox(mat_text)

            st.markdown("<br>", unsafe_allow_html=True)
            if st.form_submit_button("🔓 Submit Validation & Unlock Terminal", type="primary", use_container_width=True):
                # Verify ALL manual boxes are checked AND the auto-check is done
                if qr_check and mat_check:
                    if st.session_state.get(clean_flag_key):
                        submit_daily_checklist(current_user, current_shift, checklist_station)
                        st.toast("✅ Startup checklist fully recorded! Unlocking systems...")

                        # Clean up the session state flag
                        del st.session_state[clean_flag_key]
                        st.rerun()
                    else:
                        st.error(
                            "⚠️ You must complete and submit the Morning Cleanliness Check (Step 1) above before unlocking.")
                else:
                    st.warning("⚠️ You must check ALL manual verification items in Step 2.")

        # This function strictly stops the rest of the page from rendering until the form is passed!
        st.stop()
df_runs = get_assigned_runs_df()
active_pumps = get_active_pumps()
dt_reasons = get_downtime_reasons()

# ===================== MY STATION (multi-pourer support) =====================
# Which station's runs show in Section 1 below. Deliberately independent
# of AssignedRun.assigned_operator: any number of operators can point at
# the same station and all see — and log against — the exact same run,
# with no extra assignment needed from the manager.
#
# No separate "pick your station" widget here anymore — that was a
# redundant second click on top of the Hourly Pouring tab's own "Pump
# Station" selector (key="h_pump") further down. That selector now IS the
# station picker: Streamlit reruns this whole script top-to-bottom on
# every widget interaction and keeps a keyed widget's value in
# st.session_state across reruns, so the moment an operator changes "Pump
# Station" in that tab, the very next rerun sees the new value in
# st.session_state["h_pump"] — and Section 1 above that tab picks it up
# immediately, since Section 1 filters on `my_station` (set here from that
# same session_state key). We only need a sensible default before that
# widget has ever been rendered.
if current_role != "packer":
    station_cookie_name = f"op_station_{current_user.replace(' ', '')}"
    station_options = active_pumps if active_pumps else ["New Pump #1"]

    if "h_pump" not in st.session_state:
        saved_station = cookie_manager.get(station_cookie_name)
        st.session_state["h_pump"] = saved_station if saved_station in station_options else station_options[0]

    my_station = (st.session_state["h_pump"]
                  if st.session_state.get("h_pump") in station_options else station_options[0])

    # Keep the "remember for next time" cookie in sync whenever the
    # Hourly Pouring station selector changes.
    if cookie_manager.get(station_cookie_name) != my_station:
        cookie_manager.set(station_cookie_name, my_station, expires_at=datetime.now() + timedelta(days=90))
else:
    # Packing only ever has the one shared station — see the Packing tab
    # further down — so there's nothing to pick.
    my_station = "Pack-Out Station"

st.markdown("---")

# ===================== ROLE & SHIFT TRANSFER =====================
# Gated to real operators/packers only. This writes to
# st.session_state["user_id"] — the REAL logged-in account, never the
# name picked in the manager/admin "Impersonate Operator" debug selector
# above — so an admin/manager using this page (including while browsing
# it in impersonation mode to see what an operator sees) could otherwise
# silently downgrade their OWN account's role to Operator/Packer with one
# click, since the dropdown only ever offers those two options. That is
# exactly what happened once already; this block no longer renders at all
# for admin/manager sessions. Managers change anyone's role deliberately,
# from Admin_Panel.py, where the target user is chosen explicitly.
if current_role in ("operator", "packer"):
    with st.expander("🔄 Mid-Shift Role & Station Transfer", expanded=False):
        st.caption("Update your assignment if you are pulled to a different station or shift.")

        t_col1, t_col2, t_col3 = st.columns(3)
        with t_col1:
            role_opts = ["Operator", "Packer"]
            current_role_cap = current_role.capitalize()
            start_role_idx = role_opts.index(current_role_cap) if current_role_cap in role_opts else 0
            new_role = st.selectbox("New Assigned Role", role_opts, index=start_role_idx)

        with t_col2:
            shift_opts = ["Shift 1", "Shift 2", "Shift 3", "Floater"]
            start_shift_idx = shift_opts.index(current_shift) if current_shift in shift_opts else 0
            new_shift = st.selectbox("New Assigned Shift", shift_opts, index=start_shift_idx)

        with t_col3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("💾 Apply Transfer", use_container_width=True):
                user_id = st.session_state.get("user_id")
                if user_id:
                    if update_user_role_and_shift(user_id, new_role, new_shift):
                        # Instantly update the session state so the UI morphs on reload
                        st.session_state["user_role"] = new_role.lower()
                        st.session_state["user_shift"] = new_shift
                        st.toast(f"✅ Successfully transferred to {new_role} on {new_shift}!")
                        st.rerun()
                else:
                    st.error("Error: Could not locate User ID.")
    st.markdown("---")

# ===================== VISUAL TANK RECONCILIATION =====================
with st.expander("👀 Calibrate Tank Level (Visual Level Check)", expanded=False):
    st.caption(
        "If physical tank sight-glasses do not match live telemetry (e.g., at "
        "shift start), perform a visual level check to force-recalibrate the "
        "reactor gauge."
    )

    df_reactors_op = get_all_reactors_df()
    if not df_reactors_op.empty:
        active_tanks = df_reactors_op[
            df_reactors_op["current_resin"].notnull()
            & (df_reactors_op["current_resin"] != "None")
        ]

        if not active_tanks.empty:
            v_col1, v_col2, v_col3 = st.columns([1.5, 1.5, 1])

            with v_col1:
                selected_tank = st.selectbox(
                    "Select Vessel", active_tanks["reactor_name"].tolist()
                )
                tank_info = active_tanks[
                    active_tanks["reactor_name"] == selected_tank
                ].iloc[0]
                st.info(
                    f"Resin: **{tank_info['current_resin']}** | Max Cap:"
                    f" **{tank_info['max_capacity_l']:,} L**"
                )

            with v_col2:
                estimated_l = st.number_input(
                    label="Actual Remaining Volume (Liters)",
                    min_value=0.0,
                    max_value=float(tank_info["max_capacity_l"]),
                    value=float(tank_info["max_capacity_l"]),
                    step=1.0,
                    help="Input the exact volume read on the tank gauge."
                )

                # Reverse calculate the percentage for the UI display
                visual_pct = (estimated_l / float(tank_info["max_capacity_l"])) * 100.0
                st.caption(f"Calculated Fill Level: ~**{visual_pct:.2f}%**")

            with v_col3:
                recon_notes = st.text_input(
                    label="Check Reason", placeholder="e.g. Exact volume calibration"
                )
                st.markdown(body="<br>", unsafe_allow_html=True)
                if st.button(
                    label="⚖️ Sync Tank Level", type="primary", use_container_width=True
                ):
                    # Calling the NEW function with the exact liters!
                    success = reconcile_reactor_liters(
                        reactor_name=selected_tank,
                        actual_liters=estimated_l,
                        operator_name=current_user,
                        notes=recon_notes,
                    )

                    if success:
                        st.toast(
                            f"✅ {selected_tank} recalibrated to exactly {estimated_l}L!"
                        )
                        st.rerun()
        else:
            st.info("No active reactor tanks currently configured with resin.")
    else:
        st.info("No reactor tanks registered in database.")

# ===================== RESIN LOOKUP REFERENCE =====================
with st.expander("⚖️ Master Resin Specification Lookup", expanded=False):
    st.caption("Quick reference for formulation targets, tolerances, and container formats.")

    op_specs_df = get_all_resin_specs_df("ALL")
    # Pre-calculate kg for quick reference
    op_specs_df["Target (kg)"] = (op_specs_df["actual_spec_g"] / 1000.0).round(4)

    op_search = st.text_input("🔍 Search by Resin Name, SKU, or Code...", key="op_resin_search")
    if op_search.strip():
        op_specs_df = op_specs_df[
            op_specs_df["resin_name"].str.contains(op_search, case=False, na=False) |
            op_specs_df["sku"].str.contains(op_search, case=False, na=False) |
            op_specs_df["resin_code"].str.contains(op_search, case=False, na=False)
            ]

    st.dataframe(
        op_specs_df[
            ["cartridge_type", "sku", "resin_name", "actual_spec_g", "min_weight_g", "max_weight_g", "Target (kg)"]],
        column_config={
            "cartridge_type": "Format",
            "sku": "SKU",
            "resin_name": "Resin Formulation",
            "actual_spec_g": "Target (g)",
            "min_weight_g": "Min (g)",
            "max_weight_g": "Max (g)"
        },
        hide_index=True,
        use_container_width=True
    )

st.markdown("---")
# ===================== SECTION 1: ACTIVE ASSIGNED RUNS =====================
st.subheader("🎯 Active Assigned Production Runs (Assigned by Manager)")

if not df_runs.empty:
    target_run_type = "Packing" if current_role == "packer" else "Pouring"
    
    # Gated by station, not by who the manager originally dispatched it
    # to — see the "My Station" picker above. Whoever is logged in and
    # pointed at this station sees (and can log against) the same run.
    active_runs = df_runs[
        (df_runs["status"].isin(["Active", "Pouring", "Queued"])) &
        (df_runs["pump_station"] == my_station) &
        (df_runs.get("run_type", "Pouring") == target_run_type)
    ]
    
    if not active_runs.empty:
        for _, run in active_runs.iterrows():
            with st.container():
                prog_pct = min(1.0, run["current_units"] / run["target_units"]) if run["target_units"] > 0 else 0.0
                is_active = run["status"] in ["Active", "Pouring"]
                
                # --- NEW PULSING UI INJECTED HERE ---
                pulse_indicator = "<span class='pulse-green'></span>" if is_active else "🟡"
                status_badge = f"{pulse_indicator} POURING LIVE" if is_active else "🟡 QUEUED / STANDBY"
                status_color = "#10B981" if is_active else "#F59E0B"

                st.markdown(f"""
<div style="background:#0D1627; border:1px solid #1E2B45; border-radius:8px; padding:14px; margin-bottom:10px;">
<div style="display:flex; justify-content:space-between; align-items:center;">
<div>
<span style="background:rgba(16, 185, 129, 0.1); color:{status_color}; font-size:0.75rem; font-weight:800; padding:4px 8px; border-radius:4px; border: 1px solid {status_color};">{status_badge}</span>
<span style="font-size:1.15rem; font-weight:800; color:#FFFFFF; margin-left:8px;">{esc(run['resin_type'])}</span>
<span style="color:#00D2FF; font-weight:700; font-size:0.85rem; margin-left:6px;">[{esc(run['cartridge_type'])}]</span>
</div>
<div style="color:#94A3B8; font-size:0.85rem;">
🛢️ <b>{esc(run.get('reactor_id', 'Reactor 1'))}</b> ({run.get('reactor_size_l', 5000):,} L) &nbsp;|&nbsp; 🏷️ <b>{esc(run['pump_station'])}</b> &nbsp;|&nbsp; 👤 Dispatched: <b>{esc(run.get('assigned_operator', '—'))}</b>
</div>
</div>
<div style="background-color: #1E2B45; border-radius: 8px; width: 100%; height: 16px; margin-top: 14px; overflow: hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);">
<div class="animated-progress-bar" style="width: {prog_pct * 100}%; height: 100%; background-color: {status_color}; transition: width 0.4s ease;"></div>
</div>
<div style="font-size: 0.8rem; color: #94A3B8; margin-top: 4px; text-align: right;">
Progress: <b style="color:#FFFFFF;">{run['current_units']:,} / {run['target_units']:,}</b> Units ({prog_pct*100:.1f}%) | Lot: {_display_lot(run.get('lot_number'), run.get('cartridge_type'))}
</div>
</div>
""", unsafe_allow_html=True)

                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button("+50 Units", key=f"p50_{run['id']}"):
                        update_assigned_run_progress(run['id'], 50, operator_name=current_user)
                        st.rerun()
                with col_btn2:
                    if st.button("+100 Units", key=f"p100_{run['id']}"):
                        update_assigned_run_progress(run['id'], 100, operator_name=current_user)
                        st.rerun()
                with col_btn3:
                    if st.button("✓ Mark Done", key=f"done_{run['id']}"):
                        update_run_status(run['id'], "Done")
                        
                        # --- NEW LOTTIE ANIMATION INJECTED HERE ---
                        with st.container():
                            if lottie_success:
                                st_lottie(lottie_success, height=200, key=f"lottie_{run['id']}")
                        
                        st.toast(f"Run {run['id']} completed!", icon="✅")
                        st.rerun()
                st.markdown("---")
    else:
        st.info(f"No active {target_run_type.lower()} runs at **{my_station}** right now. "
                f"Check with your Plant Manager, or pick a different station above if you're working elsewhere this shift.")
else:
    st.info("No production runs in database.")

# ===================== SECTION 2: DIGITAL LOGGING TRAVELER =====================

# --- NEW: AUTO-SCROLL DOWN TO LOGS ON LOGIN ---
st.markdown("<div id='log_action_area' style='padding-top: 20px;'></div>", unsafe_allow_html=True)

if not st.session_state.get("auto_scrolled_to_logs", False):
    import streamlit.components.v1 as components
    components.html(
        """
        <script>
        (function () {
            // A single fixed-delay setTimeout used to be enough, but as more
            // sections (top nav, KPI cards, checklist gate, expanders) got
            // added above the log area, rendering above it can still be
            // shifting layout well past a flat 800ms — the scroll fired
            // before the page finished settling, landing in the wrong spot
            // or appearing to do nothing. This instead polls for the target
            // and waits for its position to stop moving before scrolling.
            function getDoc() {
                try {
                    if (window.parent && window.parent.document) return window.parent.document;
                } catch (e) { /* sandboxed iframe — fall back below */ }
                return document;
            }

            var doc = getDoc();
            var attempts = 0;
            var maxAttempts = 60;   // ~6s at 100ms between checks
            var lastTop = null;
            var stableCount = 0;

            var poll = setInterval(function () {
                attempts++;
                var target = doc.getElementById('log_action_area');
                if (target) {
                    var top = target.getBoundingClientRect().top;
                    stableCount = (lastTop !== null && Math.abs(top - lastTop) < 2) ? stableCount + 1 : 0;
                    lastTop = top;
                    if (stableCount >= 2 || attempts >= maxAttempts) {
                        clearInterval(poll);
                        try {
                            target.scrollIntoView({behavior: 'smooth', block: 'start'});
                        } catch (e) { /* give up quietly */ }
                    }
                } else if (attempts >= maxAttempts) {
                    clearInterval(poll);
                }
            }, 100);
        })();
        </script>
        """,
        height=0, width=0
    )
    # Lock it so it doesn't jump around while they are typing!
    st.session_state["auto_scrolled_to_logs"] = True
# -----------------------------------------------------

plant_config = get_plant_settings()
packing_enabled = plant_config.get("enable_packing", True)

if current_role == "packer":
    if packing_enabled:
        tab_pack, tab_chat = st.tabs(["📦 Log Packing", "💬 Manager Comms"])
        tab1 = tab2 = tab3 = None
    else:
        st.error("Packing module is disabled by management.")
        st.stop()
elif current_role == "operator":
    tab1, tab2, tab3, tab_chat = st.tabs((
        "⚡ Log Hourly Pouring",
        "⚠️ Log Station Downtime",
        "📸 Cleanliness & Photo Audit",
        "💬 Manager Comms"
    ))
    tab_pack = None
else:
    if packing_enabled:
        tab1, tab_pack, tab2, tab3, tab_chat = st.tabs((
            "⚡ Log Hourly Pouring",
            "📦 Log Packing",
            "⚠️ Log Station Downtime",
            "📸 Cleanliness & Photo Audit",
            "💬 Manager Comms"
        ))
    else:
        tab1, tab2, tab3, tab_chat = st.tabs((
            "⚡ Log Hourly Pouring",
            "⚠️ Log Station Downtime",
            "📸 Cleanliness & Photo Audit",
            "💬 Manager Comms"
        ))
        tab_pack = None

# --- TAB 1: HOURLY POURING COUNT ---
if tab1 is not None:
    with tab1:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📍 1. Station & Material Setup")

        # Stacked inputs for maximum tap-target size on mobile.
        # No `index=` here on purpose: st.session_state["h_pump"] is
        # already seeded with the right default above, and this is the
        # single source of truth for "my station" — changing it here is
        # what updates Section 1's active-run list on the next rerun.
        station = st.selectbox("Pump Station", active_pumps, key="h_pump")

        cartridge = st.selectbox("Container Format",
                                 ("V2 (1L Cartridge)", "V1 (1L Cartridge)", "RPS (5L Bulk Jug)", "Pigment"),
                                 key="h_cart")
        cart_code = "RPS" if "RPS" in cartridge else (
            "V1" if "V1" in cartridge else ("Pigment" if "Pigment" in cartridge else "V2"))

        # The Resin Formulation list must always show every resin on file,
        # never just the ones whose master spec happens to be registered
        # under this specific Container Format. A resin that's only ever
        # been registered as, say, V2 can still legitimately get run
        # through a V1 cartridge one day — and the operator has to be able
        # to log that regardless of what the spec table says. cart_code
        # is only used below to prefer a cartridge-matched spec for the
        # target-weight display; it never gates which resins are selectable.
        all_specs_df = get_all_resin_specs_df("ALL")
        resin_names = sorted(all_specs_df["resin_name"].unique().tolist()) if not all_specs_df.empty else []

        resin = st.selectbox("Resin Formulation", resin_names, key="h_resin")

        cart_matched = get_all_resin_specs_df(cart_code)
        cart_matched = cart_matched[cart_matched["resin_name"] == resin] if not cart_matched.empty else cart_matched
        if not cart_matched.empty:
            spec_info = cart_matched.iloc[0]
            st.caption(f"⚖️ Target: **{spec_info['actual_spec_g']}g** | Range: **{spec_info['acceptable_range']}g**")
        else:
            matched = all_specs_df[all_specs_df["resin_name"] == resin]
            if not matched.empty:
                spec_info = matched.iloc[0]
                st.caption(f"⚖️ Target: **{spec_info['actual_spec_g']}g** | Range: **{spec_info['acceptable_range']}g** "
                           f"_(no spec on file for {cartridge} — showing this resin's spec from another Container Format)_")
            else:
                st.caption("⚖️ No weight spec on file for this resin yet — logging is still allowed.")

        # Case-/whitespace-insensitive match — pump/resin/cartridge all come
        # from the same dropdowns as the Manager Cockpit's, but incidental
        # differences (trailing space, casing) used to make this silently
        # miss and fall back to a generic lot number that wouldn't match
        # the real run, so bottle counts never reached its progress bar.
        _norm = lambda s: str(s).strip().lower()
        station_active_run = df_runs[
            (df_runs["pump_station"].apply(_norm) == _norm(station)) &
            (df_runs["resin_type"].apply(_norm) == _norm(resin)) &
            (df_runs["cartridge_type"].apply(_norm) == _norm(cart_code)) &
            (df_runs["status"].isin(["Active", "Pouring"]))
            ]
        auto_lot = str(station_active_run.iloc[0].get("lot_number",
                                                      f"LOT-{datetime.now().strftime('%Y%m%d')}-01")) if not station_active_run.empty else f"LOT-{datetime.now().strftime('%Y%m%d')}-01"

        # ==================================================================
        # 2. CARTRIDGE LOT VERIFICATION GATE
        # ------------------------------------------------------------------
        # The run's lot used to auto-fill an editable box right here, which
        # meant the form answered its own question: an operator could log a
        # full hour without ever turning a cartridge over. Now the expected
        # lot is masked and the operator types what is actually stamped on
        # the bottom of the cartridge in their hand, so nothing about this
        # gate can be satisfied from what is on screen.
        #
        # A mismatch never dead-ends anyone - it demands a reason, flags the
        # log, and alerts the manager. RPS is poured without lot labels, so
        # the gate never applies to it.
        # ==================================================================
        GATED_FORMATS = ("V1", "V2", "Pigment")
        gate_applies = cart_code in GATED_FORMATS
        expected_lot = auto_lot
        expected_is_real = not is_placeholder_lot(expected_lot)

        st.markdown("---")
        st.markdown("#### 🔒 2. Cartridge Lot Verification")

        lot_num = expected_lot
        verification = None
        pending_photo = None
        gate_ok = False
        gate_blockers = []
        extra_note = ""

        if not gate_applies:
            st.info("**RPS bulk jugs carry no lot label** — nothing to verify on this format.")
            lot_num = st.text_input("Batch Lot Number", value=auto_lot,
                                    help="Auto-fills from the active run.", key="h_lot")
            gate_ok = True

        else:
            gate_mem = st.session_state.setdefault("lot_gate_memory", {})
            mem = gate_mem.get(station)

            # The fast path exists so a per-log check doesn't decay into a
            # reflex tap. It only survives while nothing physical has changed,
            # and it re-arms into a full check every 10th log regardless.
            fast_ok = False
            if mem and expected_is_real and mem.get("entered"):
                same_material = (mem.get("expected") == expected_lot
                                 and mem.get("resin") == resin
                                 and mem.get("cart") == cart_code)
                fresh = (datetime.now() - mem.get("ts", datetime.min)) <= timedelta(hours=4)
                spot_check_due = mem.get("since_full", 0) >= 9
                fast_ok = bool(same_material and fresh and not spot_check_due)

            base_v = {
                "operator_name": current_user,
                "pump_station": station,
                "shift": current_shift,
                "cartridge_type": cart_code,
                "resin_type": resin,
                "expected_lot": expected_lot if expected_is_real else None,
            }

            if fast_ok:
                st.success(
                    f"✅ Verified at **{mem['ts'].strftime('%I:%M %p').lstrip('0')}** "
                    f"by {mem.get('by', 'this station')} — same run, same lot, same station.")
                still_reads = st.checkbox(
                    f"Cartridge in my hand still reads **L-{mem['entered']}**",
                    key="h_lot_fast_confirm")
                st.caption("A full check comes back on any change of run, lot, resin or station, "
                           "after 4 hours, and on every 10th log.")
                if still_reads:
                    gate_ok = True
                    lot_num = expected_lot
                    verification = dict(base_v, entered_lot=mem["entered"],
                                        result="verified", check_level="fast")
                else:
                    gate_blockers.append("confirm the cartridge still reads the lot shown above")

            else:
                if expected_is_real:
                    st.markdown(
                        "Expected lot for this run: &nbsp; `• • • • • • • • •` &nbsp; "
                        "<span style='color:#94A3B8; font-size:0.85rem;'>"
                        "hidden on purpose — read the cartridge, not the screen</span>",
                        unsafe_allow_html=True)
                else:
                    st.warning(
                        "No active run matched this station / resin / format, so there is no lot "
                        "to check against. Read the stamp anyway — it gets recorded against this log "
                        "instead of the placeholder the app would otherwise invent.")
                st.caption("Turn the cartridge over. The bottom is stamped `L-` followed by the lot. "
                           "Type it exactly as printed — spacing, case and the prefix don't matter.")

                entered_lot = st.text_input("L- — lot stamped on the cartridge bottom",
                                            key="h_lot_entered", placeholder="2411A0742")

                typed = entered_lot.strip()
                result = None
                reason_kind, reason_detail = "", ""

                # The E- expiry line printed under the lot is deliberately NOT typed.
                # One field is all of the operator's time this check is worth, and a
                # second one every hour is how a gate turns into a reflex. The expiry
                # is already in the photo, so the offline OCR pass can fill
                # entered_expiry / expiry_status later without adding a keystroke at
                # the station - which is why those columns still exist on the table.
                if typed:
                    if not expected_is_real:
                        result = "recorded"
                    elif lots_match(expected_lot, typed):
                        result = "verified"
                    else:
                        result = "mismatch"

                if result == "verified":
                    st.success("✅ **Lot matches this run.**")
                elif result == "recorded":
                    st.info(f"📝 Stamp recorded: **L-{typed}**. Nothing to compare it against.")
                elif result == "mismatch":
                    st.error("⛔ **STOP — DO NOT POUR.** This cartridge is not from the lot assigned "
                             "to your run. Set it aside and get your lead.")

                if result == "mismatch":
                    st.markdown("**Pulled the cartridge instead? Log the catch — it belongs in the record.**")
                    if st.button("❌ Wrong cartridge — pulled it, nothing poured",
                                 use_container_width=True, key="h_lot_reject"):
                        add_lot_verification(dict(
                            base_v, entered_lot=typed, result="rejected", check_level="full",
                            reason="Cartridge pulled at the station before pouring",
                            photo_filename=save_lot_photo(pending_photo)))
                        gate_mem.pop(station, None)
                        st.toast("Catch recorded. Nothing was logged as poured.", icon="🛑")
                        st.rerun()

                    reason_kind = st.selectbox(
                        "Logging it anyway? Say what happened.",
                        ("", "Wrong pallet staged at the station", "Label misprint or unreadable",
                         "Cartridge was relabeled", "Run lot in the MES is wrong",
                         "Lead approved the pour", "Other"),
                        key="h_lot_reason_kind")
                    reason_detail = st.text_input("Details (required)", key="h_lot_reason_detail",
                                                  placeholder="What did you and your lead decide?")

                    # Evidence is only worth the upload wait on this branch. A flagged
                    # pour is the one someone reviews later and may have to defend, and
                    # the operator is already stopped talking to their lead, so the
                    # 20-30 seconds costs nothing the situation wasn't costing anyway.
                    # Note it is NOT required to pull the cartridge above: the safe
                    # action must never be slower than the risky one.
                    st.markdown("**Photograph the stamp** — required to log a pour against a flag.")
                    photo_mode = st.radio("Stamp photo", ("Take photo", "Upload image"),
                                          horizontal=True, key="h_lot_photo_mode")
                    if photo_mode == "Take photo":
                        pending_photo = st.camera_input("Photograph the stamp", key="h_lot_cam")
                    else:
                        pending_photo = st.file_uploader("Upload a photo of the stamp",
                                                         type=["png", "jpg", "jpeg", "webp", "heic", "heif"],
                                                         key="h_lot_upload")

                if not typed:
                    gate_blockers.append("type the L- lot from the cartridge")
                if result == "mismatch" and not (reason_kind and reason_detail.strip()):
                    gate_blockers.append("pick a reason and add details before logging a flagged pour")
                if result == "mismatch" and pending_photo is None:
                    gate_blockers.append("photograph the stamp")

                gate_ok = not gate_blockers
                if gate_ok:
                    reason_text = " — ".join(p for p in (reason_kind, reason_detail.strip()) if p)
                    # On a mismatch the log carries the lot that was physically in
                    # the cartridge, not the one the run expected. The run's
                    # progress bar not moving is the point: it surfaces the problem
                    # instead of burying it under a correct-looking count.
                    lot_num = typed if (result == "mismatch" or not expected_is_real) else expected_lot
                    if result == "mismatch":
                        extra_note = (f"⚠️ LOT MISMATCH — cartridge stamped L-{typed}, "
                                      f"run expects {expected_lot}. {reason_text}")
                    verification = dict(base_v, entered_lot=typed, result=result,
                                        check_level="record" if result == "recorded" else "full",
                                        reason=reason_text or None)

        st.markdown("---")
        st.markdown("#### 📊 3. Production Output")

        # Give the Good Units its own massive full-width input
        bottles_filled = st.number_input("✅ Good Units / Containers Filled", min_value=0, value=250, step=10,
                                         key="h_filled")

        # Scrap can share a row since they are smaller numbers
        p_col1, p_col2 = st.columns(2)
        with p_col1:
            scrap_empty = st.number_input("🗑️ Scrap Empty", min_value=0, value=0, step=1, key="h_s_empty")
        with p_col2:
            scrap_filled = st.number_input("🗑️ Scrap Filled", min_value=0, value=0, step=1, key="h_s_filled")

        notes = st.text_area("Process Observations / Notes", placeholder="e.g. Target fill weight nominal...",
                             key="h_notes")

        st.markdown("<br>", unsafe_allow_html=True)
        if gate_blockers:
            st.caption("Before you can submit: " + "; ".join(gate_blockers) + ".")
        if st.button("🚀 SUBMIT POURING LOG", type="primary", use_container_width=True,
                     disabled=not gate_ok):
            # Written to disk here rather than on every rerun while they type.
            if verification is not None and pending_photo is not None:
                verification["photo_filename"] = save_lot_photo(pending_photo)

            log_notes = (notes or "").strip()
            if extra_note:
                log_notes = f"{extra_note}\n{log_notes}".strip()

            matched_run = add_hourly_log(
                operator_name=current_user,
                pump_station=station,
                shift=current_shift,
                cartridge_type=cart_code,
                resin_type=resin,
                lot_number=lot_num,
                bottles=int(bottles_filled),
                scrap_empty=int(scrap_empty),
                scrap_filled=int(scrap_filled),
                notes=log_notes,
                log_type="Hourly Bottle Count",
                verification=verification
            )

            # Arm the fast path only after a clean check. A mismatch or an
            # expired lot clears it, so the next log at this station starts
            # over with the full check.
            if gate_applies and verification is not None:
                _mem = st.session_state.setdefault("lot_gate_memory", {})
                if verification.get("result") == "verified":
                    _prev = _mem.get(station) or {}
                    _mem[station] = {
                        "expected": expected_lot,
                        "resin": resin,
                        "cart": cart_code,
                        "entered": verification.get("entered_lot", ""),
                        "ts": datetime.now(),
                        "by": current_user,
                        "since_full": (_prev.get("since_full", 0) + 1)
                                      if verification.get("check_level") == "fast" else 0,
                    }
                else:
                    _mem.pop(station, None)

            if verification and verification.get("result") in ("mismatch", "expired"):
                st.toast("Logged and flagged for the manager — the lot did not check out.", icon="⚠️")
            if matched_run:
                st.toast(f"Recorded {bottles_filled} units of {resin}! Credited to your active run.", icon="🧪")
            else:
                st.toast(
                    f"Recorded {bottles_filled} units of {resin} to Analytics — "
                    f"no active run matched this station/resin/lot, so it won't move a progress bar above.",
                    icon="⚠️")
            st.rerun()

# --- PACKING TAB ---
if tab_pack is not None:
    with tab_pack:
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("#### 📦 1. Packing Details")
        pack_station = "Pack-Out Station"
        st.info("Location: **End-of-Line / Pack-Out**")

        pack_cartridge = st.selectbox("Container Format",
                                      ("V2 (1L Cartridge)", "V1 (1L Cartridge)", "RPS (5L Bulk Jug)", "Pigment"),
                                      key="p_cart")
        p_cart_code = "RPS" if "RPS" in pack_cartridge else (
            "V1" if "V1" in pack_cartridge else ("Pigment" if "Pigment" in pack_cartridge else "V2"))

        # Same reasoning as the Hourly Pouring tab: never let the Container
        # Format filter hide a resin from the picker just because its
        # master spec isn't registered for this specific format.
        p_all_specs_df = get_all_resin_specs_df("ALL")
        p_resin_names = sorted(p_all_specs_df["resin_name"].unique().tolist()) if not p_all_specs_df.empty else []

        pack_resin = st.selectbox("Resin Formulation", p_resin_names, key="p_resin")

        p_cart_matched = get_all_resin_specs_df(p_cart_code)
        p_cart_matched = p_cart_matched[p_cart_matched["resin_name"] == pack_resin] if not p_cart_matched.empty else p_cart_matched
        matched_pack = p_cart_matched if not p_cart_matched.empty else p_all_specs_df[p_all_specs_df["resin_name"] == pack_resin]
        units_per_skid = 500
        if not matched_pack.empty:
            units_per_skid = int(matched_pack.iloc[0].get("units_per_skid", 500))

        pack_lot = st.text_input("Batch Lot Number Being Packed", value=f"LOT-{datetime.now().strftime('%Y%m%d')}-01",
                                 key="p_lot")

        st.markdown("---")
        st.markdown("#### 📊 2. Units Packed")

        units_packed = st.number_input("✅ Total Good Units Packed", min_value=1, value=units_per_skid, step=50,
                                       key="p_filled")
        skids_calculated = units_packed / units_per_skid if units_per_skid > 0 else 0
        st.caption(f"Equates to: **{skids_calculated:.2f} Skids** *(Based on {units_per_skid} units/skid)*")

        pack_notes = st.text_area("Packing Notes / Box Issues", placeholder="e.g. 2 partial boxes added to skid.",
                                  key="p_notes")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("📦 SUBMIT PACKING LOG", type="primary", use_container_width=True):
            add_hourly_log(
                operator_name=current_user,
                pump_station=pack_station,
                shift=current_shift,
                cartridge_type=p_cart_code,
                resin_type=pack_resin,
                lot_number=pack_lot,
                bottles=int(units_packed),
                scrap_empty=0,
                scrap_filled=0,
                notes=pack_notes,
                log_type="Packing Count"
            )
            st.toast(f"Packing saved! Recorded {units_packed} units.", icon="📦")
            st.rerun()
# --- TAB 2: DOWNTIME ---
if tab2 is not None:
    with tab2:
        st.subheader("Station Downtime Event Logger")
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            _dt_pump_idx = active_pumps.index(my_station) if my_station in active_pumps else 0
            dt_station = st.selectbox("Downtime Station", active_pumps, index=_dt_pump_idx, key="dt_stat")
            dt_reason = st.selectbox("Reason for Downtime", dt_reasons, key="dt_reason")
        with d_col2:
            dt_duration = st.number_input("Downtime Duration (Minutes)", min_value=1, max_value=240, value=15, step=5)
            dt_notes = st.text_input("Corrective Action Taken", placeholder="Cleaned dispensing valve nozzle.", key="dt_notes")

        if st.button("⚠️ Record Downtime Event", use_container_width=True):
            add_downtime_log(
                operator_name=current_user,
                pump_station=dt_station,
                shift=current_shift,
                reason=dt_reason,
                duration_min=int(dt_duration),
                notes=dt_notes
            )
            # --- NEW TOAST INJECTED HERE ---
            st.toast(f"Recorded {int(dt_duration)} minutes downtime.", icon="⚠️")
            st.rerun()

# --- TAB 3: CLEANLINESS & SPILL PHOTO AUDIT ---
if tab3 is not None:
    with tab3:
        st.subheader("📸 Cleanliness, Changeover & Spill Photo Audit")
        st.caption("Document station readiness, pump changeovers, end-of-shift washdowns, or resin spills.")

        a_col1, a_col2 = st.columns(2)
        with a_col1:
            audit_type = st.selectbox(
                "Audit Checklist Event",
                ("Start Of Shift (Cleanliness Check)", "End Of Shift (Cleanliness Check)", "Station / Pump Transfer Check", "Resin Spill / Containment Issue")
            )
            _aud_pump_idx = active_pumps.index(my_station) if my_station in active_pumps else 0
            audit_station = st.selectbox("Pump / Workstation", active_pumps, index=_aud_pump_idx, key="aud_pump")
            is_spill_flag = st.checkbox("⚠️ Check if this is an active resin spill / leak incident", value=("Spill" in audit_type))

        with a_col2:
            audit_notes = st.text_area("Audit Observations / Cleanliness Verification", placeholder="e.g. Moving from Alpha Fast to White V5. Dispensing nozzles flushed and drip trays clear.", key="aud_notes")

        st.markdown("#### 📷 Attach Inspection Photo")
        photo_input_method = st.radio("Photo Input Method", ("Upload Image File", "Take Live Workstation Camera Photo"), horizontal=True)

        uploaded_photo = None
        if photo_input_method == "Upload Image File":
            uploaded_photo = st.file_uploader("Upload station photo", type=["png", "jpg", "jpeg", "webp", "heic", "heif"], key="mobile_photo_upload")
        else:
            uploaded_photo = st.camera_input("Capture live photo from tablet / workstation webcam")

        if uploaded_photo is not None:
            st.image(uploaded_photo, caption="Inspection Photo Preview", width=300)

        if st.button("💾 Submit Cleanliness & Photo Audit", type="primary", use_container_width=True):
            add_cleanliness_audit(
                audit_type=audit_type,
                operator_name=current_user,
                pump_station=audit_station,
                shift=current_shift,
                resin_type="",
                notes=audit_notes,
                is_spill=is_spill_flag,
                uploaded_file=uploaded_photo
            )
            
            # --- NEW TOAST INJECTED HERE ---
            st.toast("Photo Audit successfully recorded!", icon="📸")
            st.rerun()

# --- TAB 4: MANAGER COMMS ---
if tab_chat is not None:
    with tab_chat:
        st.subheader("💬 Direct Manager Communications")
        st.caption("Send and receive messages directly with the Plant Lead.")

        chat_df = get_chat_history_df(current_user)

        # Fixed height container makes it feel like a real chat app
        with st.container(height=400):
            if not chat_df.empty:
                for _, row in chat_df.iterrows():
                    msg_time = pd.to_datetime(row['timestamp']).tz_localize("UTC").tz_convert(
                        "America/New_York").strftime("%I:%M %p")
                    is_mgr = row['is_manager_reply'] == 1

                    # Managers get a tie, operators get a hardhat
                    role, fallback_avatar = ("assistant", "👨‍💼") if is_mgr else ("user", "👷")
                    avatar = get_avatar_path(row.get("sender_avatar")) or fallback_avatar

                    with st.chat_message(role, avatar=avatar):
                        st.markdown(
                            f"**{esc(row['sender_name'])}** <span style='font-size:0.7rem; color:#94A3B8;'>{msg_time}</span>",
                            unsafe_allow_html=True)
                        st.write(row['message'])
            else:
                st.info("No messages yet. Send a message to start a conversation with management.")

        # The input box pinned to the bottom
        if prompt := st.chat_input("Send a message to management...", key="op_chat_input"):
            send_floor_message(operator_name=current_user, sender_name=current_user, message=prompt, is_manager=False)
            st.rerun()
