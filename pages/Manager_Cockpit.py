
import os
import sys
import base64
from datetime import datetime, date, timedelta

import pandas as pd
import streamlit as st
import extra_streamlit_components as stx
from dotenv import load_dotenv

load_dotenv()

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))


st.set_page_config(page_title="Manager Cockpit | Formlabs MES", page_icon="📊", layout="wide")


# ===================== DYNAMIC THEME INJECTION =====================
try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}

active_theme = st.session_state.get("preferred_theme", "Default Dark")
if active_theme not in THEMES:
    active_theme = "Default Dark"

st.markdown(THEMES[active_theme], unsafe_allow_html=True)
st.logo("assets/formlabs_logo.png")

# --- PERSISTENT AUTO-LOGIN ENGINE & SECURITY GATE ---
from database import (do_logout, check_authentication, get_plant_settings,
                      role_can_administer)

cookie_manager = stx.CookieManager(key="mgr_cookies")
try:
    from ui_shell import apply_display_preferences
    apply_display_preferences(locals().get('cookie_manager'))
except Exception:
    pass
check_authentication(cookie_manager)

if not st.session_state.get("authenticated", False):
    st.switch_page("Home.py")

if st.session_state.get("user_role") not in ["manager", "admin"]:
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

def get_base64_image(image_path):
    try:
        with open(image_path, "rb") as img_file:
            return base64.b64encode(img_file.read()).decode()
    except FileNotFoundError:
        return ""

logo_b64 = get_base64_image("assets/formlabs_logo.png")

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
    if st.session_state.get("user_role") in ["admin", "manager"]:
        st.page_link("pages/Tv_Dashboard.py", label="Launch TV Mode", icon="📺", use_container_width=True)
        st.markdown("<br>", unsafe_allow_html=True)

    if st.button("Log Out & Clear Device", type="primary", use_container_width=True, key="sidebar_logout_btn"):
        do_logout(cookie_manager)
        st.switch_page("Home.py")
        st.rerun()

# ===================== ROLE-BASED TOP NAVIGATION =====================
current_role = st.session_state.get("user_role", "operator")

st.markdown("<br>", unsafe_allow_html=True)
if role_can_administer(current_role):
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

st.markdown("---")

st.markdown(f"""
<div style="display:flex; align-items:center; margin-bottom: 5px;">
    <img src="data:image/png;base64,{logo_b64}" style="height: 60px; object-fit: contain; margin-right: 15px;">
    <h1 style="margin:0; padding:0; font-size: 2.2rem;">📊 Plant Manager — Production Records</h1>
</div>
""", unsafe_allow_html=True)
# This page used to be titled "Plant Manager Operations & Work Order Dispatch"
# and led with the work-order screen, which told anybody who opened it that
# somebody has to dispatch runs before this application does anything. Nobody
# does. Every screen in the first group reads the operators' logs and needs no
# input from a manager at all; the things a manager has to set up are grouped
# as such, at the bottom, where they belong.
st.caption("Everything here reads what the operators logged. Nothing on this page "
           "has to be filled in first.")
st.markdown("<br>", unsafe_allow_html=True)

_orders_on = not bool(get_plant_settings().get("simple_mode", True))

# ===================== GHOST PAGE LAUNCHPAD =====================
st.markdown("##### 📈 What was poured")
col1, col2, col3 = st.columns(3, gap="medium")
with col1:
    st.page_link("pages/Mgr_Historical.py", label="📈 Historical Production Trends", use_container_width=True)
    st.page_link("pages/Mgr_Scrap_Intel.py", label="📊 Scrap & Yield Intelligence", use_container_width=True)
with col2:
    st.page_link("pages/Mgr_Lot_Verification.py", label="🔒 Cartridge Lot Verification", use_container_width=True)
    st.page_link("pages/Mgr_Cleanliness.py", label="📸 Cleanliness & Photo Audits", use_container_width=True)
with col3:
    st.page_link("pages/Mgr_Google_Sync.py", label="☁️ Google Cloud Sheets Sync", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("##### 👥 The floor")
col4, col5, col6 = st.columns(3, gap="medium")
with col4:
    st.page_link("pages/Mgr_Roster.py", label="👥 Floor Staff Roster", use_container_width=True)
with col5:
    st.page_link("pages/Mgr_Floor_Comms.py", label="💬 Floor Communications", use_container_width=True)
with col6:
    st.page_link("pages/Tv_Dashboard.py", label="📺 Floor Display (TV Mode)", use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown("##### ⚙️ Setup — optional")
st.caption("None of this is needed to log a pour. Set a piece up when you want the "
           "answer it gives you.")
col7, col8, col9 = st.columns(3, gap="medium")
with col7:
    st.page_link("pages/Mgr_Assigned_Runs.py", label="🎯 Work Orders & Assigned Runs",
                 use_container_width=True,
                 disabled=not _orders_on)
    if not _orders_on:
        st.caption("Off while this plant runs as a logging system.")
    # In logging mode the manager is the administrator, and the console is
    # where the mode itself is set - so it belongs in this group rather than
    # only in the sidebar, where somebody looking for "where do I add a pump"
    # would not think to look.
    if role_can_administer(current_role):
        st.page_link("pages/Admin_Panel.py", label="🛡️ Accounts, Equipment & Settings",
                     use_container_width=True)
        if not _orders_on:
            st.caption("Yours to run: PINs, pumps, resins, backups, and the mode above.")
with col8:
    st.page_link("pages/Mgr_Resin_Canvas.py", label="⚖️ Master Resin Specifications", use_container_width=True)
    st.caption("Target fill weights, so an out-of-band pour flags itself.")
with col9:
    st.page_link("pages/Mgr_Log_Management.py", label="🗑️ Log Management & Cleanup", use_container_width=True)
    # Added because it was built and then left with no way in: nothing in the
    # app linked to it, so the contrast audit and the component gallery could
    # only be reached by typing the URL.
    st.page_link("pages/Mgr_Theme_Gallery.py", label="🎨 Theme Gallery & Contrast Audit",
                 use_container_width=True)
