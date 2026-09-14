"""Notes tab (manager comms).

Moved out of Operator_Form.py verbatim.

This used to be called "Direct Manager Communications" and was captioned
as messaging the Plant Lead directly. It renders as a chat, sits on the
operator's own screen, and every signal it gave said somebody was on the
other end of it - but nothing in this application tells a manager a
message has arrived. Not on their home screen, not in the sidebar, not on
the wall display. A manager sat at the PC all day would never know.

So an operator typing "pump 2 is leaking" here and going back to work
believing it had been reported was the application absorbing an urgent
message and silently dropping it. The words are the dangerous part, and
they are the cheap part to fix: this is a written note that gets read
when somebody next looks, and it now says so before anything is typed
rather than after nobody answers.
"""
import pandas as pd
import streamlit as st

from database import esc, get_avatar_path, get_chat_history_df, send_floor_message


def render(ctx):
    current_user = ctx.current_user

    st.subheader("📋 Notes")
    st.caption("A written note for the plant lead — it stays on the record with "
               "your name and the time on it.")
    st.warning("**Nobody is watching this in real time.** Use the radio or find a "
               "lead in person for anything urgent, or anything unsafe. This is for "
               "the things that would otherwise be forgotten by the end of shift — "
               "running low on a material, a machine that needs looking at, "
               "something that keeps costing time.")

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
            st.info("Nothing noted yet. Anything you write here is kept with your "
                    "name and the time, and stays on the record.")

    # The input box pinned to the bottom
    if prompt := st.chat_input("Write a note for management…", key="op_chat_input"):
        send_floor_message(operator_name=current_user, sender_name=current_user, message=prompt, is_manager=False)
        st.rerun()
