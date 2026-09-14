"""Downtime tab.

Moved out of Operator_Form.py verbatim. Already converted to a plain
st.form (rather than free-running widgets) in the perf pass before this
split - every field here is independent, nothing on this tab reads
another field's live value the way the Pouring tab's changeover warning
does, so wrapping it in a form means the page only reruns once, when the
button is pressed, instead of on every keystroke.
"""
import streamlit as st

from database import add_downtime_log, flash


def render(ctx):
    current_user = ctx.current_user
    current_shift = ctx.current_shift
    active_pumps = ctx.active_pumps
    my_station = ctx.my_station
    dt_reasons = ctx.dt_reasons

    st.subheader("Station Downtime Event Logger")
    with st.form("downtime_form"):
        d_col1, d_col2 = st.columns(2)
        with d_col1:
            _dt_pump_idx = active_pumps.index(my_station) if my_station in active_pumps else 0
            dt_station = st.selectbox("Downtime Station", active_pumps, index=_dt_pump_idx, key="dt_stat")
            dt_reason = st.selectbox("Reason for Downtime", dt_reasons, key="dt_reason")
        with d_col2:
            dt_duration = st.number_input("Downtime Duration (Minutes)", min_value=1, max_value=240, value=15, step=5)
            dt_notes = st.text_input("Corrective Action Taken", placeholder="Cleaned dispensing valve nozzle.", key="dt_notes")

        if st.form_submit_button("⚠️ Record Downtime Event", use_container_width=True):
            add_downtime_log(
                operator_name=current_user,
                pump_station=dt_station,
                shift=current_shift,
                reason=dt_reason,
                duration_min=int(dt_duration),
                notes=dt_notes
            )
            flash(f"Recorded {int(dt_duration)} minutes downtime.", "⚠️")
            st.rerun()
