
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from database import get_operators_with_messages, get_active_operators, get_chat_history_df, send_floor_message, do_logout

st.set_page_config(page_title="Floor Comms | Formlabs MES", page_icon="💬", layout="wide")
from database import esc, get_avatar_path

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
from ui_shell import render_shell
cookie_manager = render_shell()
current_role = st.session_state.get("user_role", "operator")

st.subheader("💬 Live Floor Communications")

active_chat_ops = get_operators_with_messages()
all_ops = get_active_operators()
display_ops = sorted(list(set(active_chat_ops + all_ops)))

if display_ops:
    chat_col1, chat_col2 = st.columns([1, 3])
    with chat_col1:
        selected_chat_op = st.radio("Operators", display_ops, label_visibility="collapsed", key="mgr_chat_op_selector")
    with chat_col2:
        if selected_chat_op:
            st.markdown(f"#### Chat with {selected_chat_op}")
            chat_df = get_chat_history_df(selected_chat_op)
            with st.container(height=400):
                if not chat_df.empty:
                    for _, row in chat_df.iterrows():
                        msg_time = pd.to_datetime(row['timestamp']).tz_localize("UTC").tz_convert("America/New_York").strftime("%I:%M %p")
                        is_mgr = row['is_manager_reply'] == 1
                        role, fallback_avatar = ("user", "👨‍💼") if is_mgr else ("assistant", "👷")
                        avatar = get_avatar_path(row.get("sender_avatar")) or fallback_avatar
                        with st.chat_message(role, avatar=avatar):
                            st.markdown(f"**{esc(row['sender_name'])}** <span style='font-size:0.7rem; color:#94A3B8;'>{msg_time}</span>", unsafe_allow_html=True)
                            st.write(row['message'])
                else:
                    st.info(f"No messages yet with {selected_chat_op}.")
            if prompt := st.chat_input(f"Reply to {selected_chat_op}...", key="mgr_chat_input_box"):
                send_floor_message(selected_chat_op, "Plant Lead", prompt, is_manager=True)
                st.rerun()
