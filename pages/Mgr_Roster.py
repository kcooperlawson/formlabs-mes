
import os
import sys

import streamlit as st
from datetime import datetime, timedelta

# --- SYSTEM PATH ENFORCEMENT ---
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import get_all_users_df, create_user, update_user_pin, do_logout

st.set_page_config(page_title="Staff Roster | Formlabs MES", page_icon="👥", layout="wide")


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
import time
cookie_manager = render_shell()
current_role = st.session_state.get("user_role", "operator")

st.subheader("👥 Floor Personnel Administration (Manager Access)")
st.info("💡 **Security Notice:** Managers can provision and manage Floor Personnel. IT Admins manage management accounts and terminations.")

df_users = get_all_users_df()
u_col1, u_col2 = st.columns((1, 2.5))

with (u_col1):
    st.markdown("#### ➕ Provision Floor Personnel")
    with st.form("mgr_create_user_form", clear_on_submit=True):
        new_fullname = st.text_input("Full Name")
        new_email = st.text_input("Work Email")
        new_username = st.text_input("Username / ID")
        new_pin = st.text_input("PIN / Password", type="password")
        new_role = st.selectbox("Role", ("Operator", "Packer"))
        new_shift = st.selectbox("Assigned Shift", ("Shift 1", "Shift 2", "Floater"))
        new_target = st.number_input("Target Rate (L/h)", value=400.0, step=10.0)

        if st.form_submit_button("Create Personnel", type="primary", use_container_width=True):
            if create_user(new_username, new_email, new_pin, new_fullname, new_role.lower(), float(new_target), new_shift):
                st.toast("✅ Account created successfully!")
                st.rerun()
            else:
                st.error("❌ Username or email already exists.")

with u_col2:
    st.markdown("#### 📋 Floor Roster")
    if not df_users.empty:
        floor_df = df_users[df_users["role"].isin(["operator", "packer"])]
        if not floor_df.empty:
            st.markdown(f'<div style="overflow-x: auto;">{floor_df[["id", "full_name", "username", "role", "shift"]].to_html(index=False)}</div>', unsafe_allow_html=True)
        else:
            st.caption("No floor personnel found.")

st.markdown("<br>", unsafe_allow_html=True)

with st.expander("🔑 Reset Floor Operator PIN", expanded=False):
    if not df_users.empty:
        floor_df = df_users[df_users["role"].isin(["operator", "packer"])]
        if not floor_df.empty:
            target_user = st.selectbox("Select Personnel", floor_df["username"].tolist(), key="mgr_rst_usr")
            new_temp_pin = st.text_input("New PIN", type="password", key="mgr_rst_pin")
            if st.button("💾 Reset PIN", type="primary"):
                user_row = floor_df[floor_df["username"] == target_user].iloc[0]
                update_user_pin(int(user_row["id"]), new_temp_pin)
                st.toast(f"✅ PIN updated for '{target_user}'.")
                st.rerun()
