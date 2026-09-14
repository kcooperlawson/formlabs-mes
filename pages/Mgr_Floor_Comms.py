
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from database import get_operators_with_messages, get_active_operators, get_chat_history_df, send_floor_message, do_logout

st.set_page_config(page_title="Floor Comms | Formlabs MES", page_icon="💬", layout="wide")
from database import esc, get_avatar_path


try:
    from themes import THEMES
except ImportError:
    THEMES = {"Formlabs Forge": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Formlabs Forge"), THEMES["Formlabs Forge"]), unsafe_allow_html=True)

# Restore the session before deciding whether to refuse it. Without this the
# role check below runs against an empty session on any cold load - a refresh,
# a bookmark, a link opened in a new tab - and answers Access Denied to a
# manager who has every right to be here. It only ever appeared to work
# because arriving from another page carried the session in memory, and the
# one thing nobody does while testing is press F5.
import extra_streamlit_components as _stx
from database import can
from database import check_authentication as _check_auth
_check_auth(_stx.CookieManager(key="auth_floor_comms"))

if not st.session_state.get("authenticated", False) or not can("view_manager_cockpit"):
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
from ui_shell import render_shell
cookie_manager = render_shell()
current_role = st.session_state.get("user_role", "operator")

# Called "Live Floor Communications" until now, which it is not: nothing in
# this application tells anybody a note has arrived, so it is read when
# somebody opens this page and not before. The operator's side says so plainly
# now, and so does this one - a page that describes itself as live is how a
# note sits unread for two days while everyone assumes otherwise.
st.subheader("📋 Notes from the Floor")
st.caption("Written notes from operators, read when you open this page. Nothing here "
           "alerts anybody, so it is not where an urgent problem will reach you.")

active_chat_ops = get_operators_with_messages()
all_ops = get_active_operators()
display_ops = sorted(list(set(active_chat_ops + all_ops)))

if display_ops:
    # Everyone on the floor is listed, which means the ones who have actually
    # written something are indistinguishable from the ones who have not - and
    # finding them meant clicking every name. A dot costs nothing and is the
    # difference between reading this page and giving up on it.
    _written = set(active_chat_ops)
    _label = {(f"● {op}" if op in _written else f"○ {op}"): op for op in display_ops}
    _ordered = ([k for k in _label if k.startswith("●")] +
                [k for k in _label if k.startswith("○")])

    chat_col1, chat_col2 = st.columns([1, 3])
    with chat_col1:
        st.caption(f"● has written ({len(_written)})")
        selected_chat_op = _label[st.radio("Operators", _ordered,
                                           label_visibility="collapsed",
                                           key="mgr_chat_op_selector")]
    with chat_col2:
        if selected_chat_op:
            st.markdown(f"#### Notes from {selected_chat_op}")
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
                    st.info(f"{selected_chat_op} has not written anything.")
            if prompt := st.chat_input(f"Reply to {selected_chat_op} — they will see it next time they open their form…", key="mgr_chat_input_box"):
                send_floor_message(selected_chat_op, "Plant Lead", prompt, is_manager=True)
                st.rerun()
