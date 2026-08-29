import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) 
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta

# --- NEW IMPORTS FOR ANIMATION ---
from streamlit_lottie import st_lottie
import requests

from database import (
    add_hourly_log,
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
)
import base64

import extra_streamlit_components as stx
cookie_manager = stx.CookieManager(key="op_cookies")

# Load the Lottie Animation once
def load_lottieurl(url):
    r = requests.get(url)
    if r.status_code != 200:
        return None
    return r.json()

lottie_success = load_lottieurl("https://assets10.lottiefiles.com/packages/lf20_lk80fpsm.json")

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""

logo_b64 = get_base64_image("assets/formlabs_logo.png")

st.set_page_config(page_title="Operator Terminal | Formlabs MES", page_icon="📝", layout="wide")

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
import extra_streamlit_components as stx



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
            st.rerun()
    else:
        # THE DOUBLE-TAKE: Give the browser 0.2 seconds to send the cookie!
        if not st.session_state["auth_check_passed"]:
            st.session_state["auth_check_passed"] = True
            st.rerun()
        else:
            # If it checked twice and STILL no cookie, they are truly logged out.
            st.warning("🔒 Session Expired. Please log in.")
            st.switch_page("Home.py")
            st.stop()

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
            new_avatar = st.file_uploader("Upload Avatar", type=["png", "jpg", "jpeg", "webp"], key="set_avatar_upload")
            if st.button("💾 Save Avatar", type="primary", use_container_width=True):
                if new_avatar:
                    from database import update_user_avatar

                    update_user_avatar(st.session_state["user_id"], new_avatar)
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
    if not has_completed_daily_checklist(current_user, current_shift):
        st.error("🛑 **TERMINAL LOCKED: PRE-SHIFT VALIDATION REQUIRED**")
        st.info(
            f"Welcome, {current_user}. Please complete your mandatory startup checklist for **{current_shift}** before accessing the production modules.")

        # --- NEW: Cookie Check to survive page refreshes ---
        clean_cookie_name = f"clean_chk_{current_user.replace(' ', '')}"

        # If the cookie has today's date, they already submitted the photo!
        if cookie_manager.get(clean_cookie_name) == str(date.today()):
            st.session_state["pre_shift_clean_done"] = True
        elif "pre_shift_clean_done" not in st.session_state:
            st.session_state["pre_shift_clean_done"] = False

        st.markdown("### 📋 Daily Startup Checklist")

        # --- STEP 1: THE AUTO-CHECK (CLEANLINESS AUDIT) ---
        if not st.session_state["pre_shift_clean_done"]:
            with st.expander("📸 Step 1: Perform & Submit Morning Cleanliness Check", expanded=True):
                st.caption("Submit your start-of-shift photo audit here to satisfy this requirement.")

                active_pumps_list = get_active_pumps()
                audit_station = st.selectbox("Assigned Pump / Workstation", active_pumps_list, key="pre_pump")
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

                        st.session_state["pre_shift_clean_done"] = True
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
                    if st.session_state.get("pre_shift_clean_done"):
                        submit_daily_checklist(current_user, current_shift)
                        st.toast("✅ Startup checklist fully recorded! Unlocking systems...")

                        # Clean up the session state flag
                        del st.session_state["pre_shift_clean_done"]
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

# ===================== ROLE & SHIFT TRANSFER =====================
with st.expander("🔄 Mid-Shift Role & Station Transfer", expanded=False):
    st.caption("Update your assignment if you are pulled to a different station or shift.")

    t_col1, t_col2, t_col3 = st.columns(3)
    with t_col1:
        role_opts = ["Operator", "Packer"]
        current_role_cap = current_role.capitalize()
        # Fallback in case a manager uses this
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
    
    active_runs = df_runs[
        (df_runs["status"].isin(["Active", "Pouring", "Queued"])) & 
        (df_runs["assigned_operator"] == current_user) &
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
<span style="font-size:1.15rem; font-weight:800; color:#FFFFFF; margin-left:8px;">{run['resin_type']}</span>
<span style="color:#00D2FF; font-weight:700; font-size:0.85rem; margin-left:6px;">[{run['cartridge_type']}]</span>
</div>
<div style="color:#94A3B8; font-size:0.85rem;">
🛢️ <b>{run.get('reactor_id', 'Reactor 1')}</b> ({run.get('reactor_size_l', 5000):,} L) &nbsp;|&nbsp; 🏷️ <b>{run['pump_station']}</b>
</div>
</div>
<div style="background-color: #1E2B45; border-radius: 8px; width: 100%; height: 16px; margin-top: 14px; overflow: hidden; box-shadow: inset 0 2px 4px rgba(0,0,0,0.5);">
<div class="animated-progress-bar" style="width: {prog_pct * 100}%; background-color: {status_color};"></div>
</div>
<div style="font-size: 0.8rem; color: #94A3B8; margin-top: 4px; text-align: right;">
Progress: <b style="color:#FFFFFF;">{run['current_units']:,} / {run['target_units']:,}</b> Units ({prog_pct*100:.1f}%) | Lot: {run.get('lot_number', 'N/A')}
</div>
</div>
""", unsafe_allow_html=True)

                col_btn1, col_btn2, col_btn3 = st.columns(3)
                with col_btn1:
                    if st.button("+50 Units", key=f"p50_{run['id']}"):
                        update_assigned_run_progress(run['id'], 50)
                        st.rerun()
                with col_btn2:
                    if st.button("+100 Units", key=f"p100_{run['id']}"):
                        update_assigned_run_progress(run['id'], 100)
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
        st.info("No active production runs assigned to you. Check with your Plant Manager.")
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
            // Wait a split-second for the charts and UI to finish rendering above
            setTimeout(function() {
                var target = window.parent.document.getElementById('log_action_area');
                if (target) {
                    target.scrollIntoView({behavior: 'smooth', block: 'start'});
                }
            }, 800); 
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

        # Stacked inputs for maximum tap-target size on mobile
        station = st.selectbox("Pump Station", active_pumps, key="h_pump")

        cartridge = st.selectbox("Container Format",
                                 ("V2 (1L Cartridge)", "V1 (1L Cartridge)", "RPS (5L Bulk Jug)", "Pigment"),
                                 key="h_cart")
        cart_code = "RPS" if "RPS" in cartridge else (
            "V1" if "V1" in cartridge else ("Pigment" if "Pigment" in cartridge else "V2"))

        specs_df = get_all_resin_specs_df(cart_code)
        if specs_df.empty:
            specs_df = get_all_resin_specs_df("ALL")
        resin_names = sorted(specs_df["resin_name"].unique().tolist())

        resin = st.selectbox("Resin Formulation", resin_names, key="h_resin")
        matched = specs_df[specs_df["resin_name"] == resin]
        if not matched.empty:
            spec_info = matched.iloc[0]
            st.caption(f"⚖️ Target: **{spec_info['actual_spec_g']}g** | Range: **{spec_info['acceptable_range']}g**")

        station_active_run = df_runs[
            (df_runs["pump_station"] == station) &
            (df_runs["resin_type"] == resin) &
            (df_runs["cartridge_type"] == cart_code) &
            (df_runs["status"].isin(["Active", "Pouring"]))
            ]
        auto_lot = str(station_active_run.iloc[0].get("lot_number",
                                                      f"LOT-{datetime.now().strftime('%Y%m%d')}-01")) if not station_active_run.empty else f"LOT-{datetime.now().strftime('%Y%m%d')}-01"

        lot_num = st.text_input("Batch Lot Number", value=auto_lot, help="Auto-fills from active run.", key="h_lot")

        st.markdown("---")
        st.markdown("#### 📊 2. Production Output")

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
        if st.button("🚀 SUBMIT POURING LOG", type="primary", use_container_width=True):
            add_hourly_log(
                operator_name=current_user,
                pump_station=station,
                shift=current_shift,
                cartridge_type=cart_code,
                resin_type=resin,
                lot_number=lot_num,
                bottles=int(bottles_filled),
                scrap_empty=int(scrap_empty),
                scrap_filled=int(scrap_filled),
                notes=notes,
                log_type="Hourly Bottle Count"
            )
            st.toast(f"Recorded {bottles_filled} units of {resin}!", icon="🧪")
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

        p_specs_df = get_all_resin_specs_df(p_cart_code)
        if p_specs_df.empty:
            p_specs_df = get_all_resin_specs_df("ALL")
        p_resin_names = sorted(p_specs_df["resin_name"].unique().tolist())

        pack_resin = st.selectbox("Resin Formulation", p_resin_names, key="p_resin")

        matched_pack = p_specs_df[p_specs_df["resin_name"] == pack_resin]
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
            dt_station = st.selectbox("Downtime Station", active_pumps, key="dt_stat")
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
            audit_station = st.selectbox("Pump / Workstation", active_pumps, key="aud_pump")
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
                    role, avatar = ("assistant", "👨‍💼") if is_mgr else ("user", "👷")

                    with st.chat_message(role, avatar=avatar):
                        st.markdown(
                            f"**{row['sender_name']}** <span style='font-size:0.7rem; color:#94A3B8;'>{msg_time}</span>",
                            unsafe_allow_html=True)
                        st.write(row['message'])
            else:
                st.info("No messages yet. Send a message to start a conversation with management.")

        # The input box pinned to the bottom
        if prompt := st.chat_input("Send a message to management...", key="op_chat_input"):
            send_floor_message(operator_name=current_user, sender_name=current_user, message=prompt, is_manager=False)
            st.rerun()