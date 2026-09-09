"""Batch history: how long resin sat in a vessel, and how long QC had it.

Three questions came down from management and they are all the same missing
thing: when did this go to QC, when did it come back, and how long has it been
sitting in that reactor.

The reactor half needs nothing typed. A filling opens when a vessel is changed
over and closes at the next changeover, both of which the floor already does at
the pump, so those durations are as good as the changeover confirmations.

The QC half is two times a manager enters, and this page says so out loud. A
turnaround figure built from when somebody got to a screen is a measure of data
entry, not of QC, and a number on a management report with nothing under it is
worse than a blank - somebody will act on it.
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Batch History | Formlabs MES", page_icon="🧪", layout="wide")

from database import esc, get_batches, do_logout
from components import empty_state

try:
    from themes import THEMES
except ImportError:
    THEMES = {"Default Dark": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Default Dark"),
                       THEMES["Default Dark"]), unsafe_allow_html=True)

# Restore the session before deciding whether to refuse it - see the note in
# Mgr_Cleanliness.py. A cold load on a bookmark is a manager, not an intruder.
import extra_streamlit_components as _stx
from database import can
from database import check_authentication as _check_auth
_check_auth(_stx.CookieManager(key="auth_batch_history"))

if not st.session_state.get("authenticated", False) or not can("view_manager_cockpit"):
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

from ui_shell import render_shell
cookie_manager = render_shell()

st.subheader("🧪 Batch History — reactor dwell and QC turnaround")

_days = st.selectbox("Show fillings started in the last",
                     (7, 14, 30, 90, 365), index=2,
                     format_func=lambda d: f"{d} days")
rows = get_batches(since=datetime.now() - timedelta(days=int(_days)), limit=800)

if not rows:
    empty_state(
        "🧪", "No batches recorded yet",
        "A filling is opened when a vessel is changed over to a resin, so the "
        "first one appears here after the next changeover is confirmed at a "
        "pump. Vessels that already held something were given an open filling "
        "when this was switched on.")
    st.stop()

df = pd.DataFrame(rows)

# A duration is None until both ends of it exist, and a column of nothing but
# None arrives as text - so every average and every rounding below would fail
# on exactly the case this page is most likely to meet on its first day: a
# plant that has batches and has not recorded any QC yet.
for _col in ("hours_in_reactor", "hours_at_qc"):
    df[_col] = pd.to_numeric(df[_col], errors="coerce")
for _col in ("filled_at", "emptied_at", "qc_sent_at", "qc_result_at"):
    df[_col] = pd.to_datetime(df[_col], errors="coerce")

# ------------------------------------------------------------ the headline --
_open = df[df["open"]]
_at_qc = df[df["qc_open"]]
_done = df[(~df["qc_open"]) & df["hours_at_qc"].notna()]
_closed = df[~df["open"]]

k1, k2, k3, k4 = st.columns(4)
k1.metric("Fillings in this window", len(df))
k2.metric("Sitting in a vessel now", len(_open))
k3.metric("Waiting on QC", len(_at_qc),
          help="A sample has gone and the result is not back.")
k4.metric("Average QC turnaround",
          f"{_done['hours_at_qc'].mean():,.1f} h" if len(_done) else "—",
          help="Only the ones where both times were entered.")

c1, c2, c3 = st.columns(3)
c1.metric("Average time in a vessel",
          f"{_closed['hours_in_reactor'].mean():,.1f} h" if len(_closed) else "—",
          help="Fillings that have been emptied. The open ones are still counting.")
c2.metric("Longest still sitting",
          f"{_open['hours_in_reactor'].max():,.0f} h" if len(_open) else "—")
c3.metric("Longest wait on QC",
          f"{_at_qc['hours_at_qc'].max():,.0f} h" if len(_at_qc) else "—")

# The one that gets somebody out of their chair: what is waiting right now,
# oldest first. A count of things waiting is a statistic; a list with an age
# against each is a job.
if len(_at_qc):
    st.markdown("#### Out at QC now")
    for _, b in _at_qc.sort_values("hours_at_qc", ascending=False).iterrows():
        _h = b["hours_at_qc"]
        _tone = "#EF4444" if _h and _h > 48 else "#F59E0B" if _h and _h > 24 else "#38BDF8"
        st.markdown(
            f"<div style='border-left:3px solid {_tone}; padding:6px 12px; "
            f"margin-bottom:6px; background:rgba(128,128,128,0.06);'>"
            f"<b>{esc(b['reactor_name'])}</b> · {esc(b['resin_type'] or 'resin not recorded')}"
            f" &nbsp;·&nbsp; <span style='color:{_tone}; font-weight:700;'>"
            f"{_h:,.0f} h at QC</span></div>", unsafe_allow_html=True)

if len(_open):
    _no_qc = _open[(_open["qc_result"] == "") & (~_open["qc_open"])]
    if len(_no_qc):
        st.caption(f"{len(_no_qc)} filling(s) in a vessel with no QC recorded "
                   f"at all. That is a blank, not a pass.")

# --------------------------------------------------------------- the table --
st.markdown("#### Every filling")
view = df.copy()
view["Filled"] = view["filled_at"].dt.strftime("%d %b %H:%M").fillna("unknown")
view["Emptied"] = view["emptied_at"].dt.strftime("%d %b %H:%M").fillna("still in use")
view["In vessel (h)"] = view["hours_in_reactor"].round(1)
view["Sent to QC"] = view["qc_sent_at"].dt.strftime("%d %b %H:%M").fillna("—")
view["Back from QC"] = view["qc_result_at"].dt.strftime("%d %b %H:%M").fillna("—")
view["At QC (h)"] = view["hours_at_qc"].round(1)
view["Result"] = view["qc_result"].replace({"": "—", "pass": "pass",
                                            "fail": "FAIL", "hold": "on hold"})
st.dataframe(
    view[["reactor_name", "resin_type", "Filled", "Emptied", "In vessel (h)",
          "Sent to QC", "Back from QC", "At QC (h)", "Result", "qc_by"]].rename(
        columns={"reactor_name": "Vessel", "resin_type": "Resin",
                 "qc_by": "Recorded by"}),
    use_container_width=True, hide_index=True)

st.download_button(
    "⬇️ Download as CSV", view.to_csv(index=False).encode("utf-8"),
    file_name=f"batch_history_{datetime.now():%Y%m%d}.csv", mime="text/csv")

st.caption(
    "Times in a vessel come from changeovers confirmed at the pump. QC times "
    "are entered by hand on the reactor page, so they are only as good as when "
    "somebody enters them - which is worth saying before anybody averages them.")
