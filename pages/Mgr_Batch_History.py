"""Batch history: how long resin sat in a vessel, and how long QC had it.

Three questions came down from management and they are all the same missing
thing: when did this go to QC, when did it come back, and how long has it
been sitting in that reactor.

The reactor half used to rely on one signal only: a filling closed at the
next changeover, because that is a real event the floor already produces.
The trouble is a tank that runs dry and sits empty for a while before the
next changeover reads as if the old resin were still sitting in it the whole
time - the dwell figure was measuring "time until somebody poured something
else in," not "time the resin was actually there." An operator can now mark
a tank empty the moment it runs dry, from the pouring form itself, so the
common case is right without anyone touching this screen; the changeover
close still fires as a backstop for whoever's tank was marked empty in
neither way, so a filling can never get stuck open forever.

The QC half is two times a manager enters, and this page says so out loud. A
turnaround figure built from when somebody got to a screen is a measure of
data entry, not of QC, and a number on a management report with nothing
under it is worse than a blank - somebody will act on it. QC entry used to
live on the reactor page; it is entered here now, next to the reporting it
feeds, rather than requiring a trip to a different screen for the same
batch.
"""
import sys
import os
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="Batch History | Formlabs MES", page_icon="🧪", layout="wide")

from database import esc, get_batches, set_batch_qc, do_logout, can
from components import empty_state

try:
    from themes import THEMES
except ImportError:
    THEMES = {"Formlabs Forge": "<style>.stApp { background-color: #02040A !important; color: #E2E8F0 !important; }</style>"}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Formlabs Forge"),
                       THEMES["Formlabs Forge"]), unsafe_allow_html=True)

# Restore the session before deciding whether to refuse it - see the note in
# Mgr_Cleanliness.py. A cold load on a bookmark is a manager, not an intruder.
import extra_streamlit_components as _stx
from database import check_authentication as _check_auth
_check_auth(_stx.CookieManager(key="auth_batch_history"))

if not st.session_state.get("authenticated", False) or not can("view_manager_cockpit"):
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

from ui_shell import render_shell
cookie_manager = render_shell()

# ------------------------------------------------------------ chart theme --
# Same transparent-canvas / muted-grid treatment as Live Reactors and
# Analytics Hub, so a chart on this page reads as part of the same app
# rather than a bolted-on report. Status colours below (pass/hold/fail/at
# QC) are the exact hexes the pouring form and Live Reactors already use for
# the same meanings, so a colour never has to be relearned per screen.
_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#94A3B8", family="sans-serif"),
    margin=dict(t=30, b=20, l=10, r=10),
    xaxis=dict(showgrid=False, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False),
)
_C_DWELL = "#00D2FF"
_C_QC = "#38BDF8"
_C_WARN = "#F59E0B"
_C_BAD = "#EF4444"
_C_MUTED = "#64748B"


def _stat_card(label, value, sub="", accent=_C_DWELL) -> str:
    """One gradient-glass stat tile, matching the vessel cards on Live Reactors."""
    _sub_html = (f'<div style="font-size:0.72rem; color:{_C_MUTED}; margin-top:2px;">{esc(sub)}</div>'
                 if sub else "")
    return (
        f'<div style="background:linear-gradient(180deg, #0D1627 0%, #080D1A 100%); '
        f'border:1px solid {accent}; border-radius:10px; padding:14px 16px; height:100%;">'
        f'<div style="font-size:0.65rem; font-weight:800; color:#94A3B8; '
        f'letter-spacing:0.1em; text-transform:uppercase;">{esc(label)}</div>'
        f'<div style="font-size:1.6rem; font-weight:900; color:#FFFFFF; margin-top:4px;">{value}</div>'
        f'{_sub_html}</div>'
    )


st.subheader("🧪 Batch History — reactor dwell and QC turnaround")

_days = st.selectbox("Show fillings started in the last",
                     (7, 14, 30, 90, 365), index=2,
                     format_func=lambda d: f"{d} days")
rows = get_batches(since=datetime.now() - timedelta(days=int(_days)), limit=800)

if not rows:
    empty_state(
        "No batches recorded yet",
        "A filling is opened when a vessel is changed over to a resin, so the "
        "first one appears here after the next changeover is confirmed at a "
        "pump. Vessels that already held something were given an open filling "
        "when this was switched on.",
        icon="🧪")
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
with k1:
    st.markdown(_stat_card("Fillings in window", f"{len(df):,}"), unsafe_allow_html=True)
with k2:
    st.markdown(_stat_card("Sitting in a vessel now", f"{len(_open):,}"), unsafe_allow_html=True)
with k3:
    st.markdown(_stat_card("Waiting on QC", f"{len(_at_qc):,}",
                           sub="Sample gone, result not back.", accent=_C_QC),
                unsafe_allow_html=True)
with k4:
    st.markdown(_stat_card("Avg QC turnaround",
                           f"{_done['hours_at_qc'].mean():,.1f} h" if len(_done) else "—",
                           sub="Only where both times were entered.", accent=_C_QC),
                unsafe_allow_html=True)

st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

c1, c2, c3 = st.columns(3)
with c1:
    st.markdown(_stat_card("Avg time in a vessel",
                           f"{_closed['hours_in_reactor'].mean():,.1f} h" if len(_closed) else "—",
                           sub="Fillings that have been emptied."),
                unsafe_allow_html=True)
with c2:
    st.markdown(_stat_card("Longest still sitting",
                           f"{_open['hours_in_reactor'].max():,.0f} h" if len(_open) else "—"),
                unsafe_allow_html=True)
with c3:
    st.markdown(_stat_card("Longest wait on QC",
                           f"{_at_qc['hours_at_qc'].max():,.0f} h" if len(_at_qc) else "—",
                           accent=_C_QC),
                unsafe_allow_html=True)

st.markdown("---")

# ------------------------------------------------------------------ charts --
chart1, chart2 = st.columns(2)

with chart1:
    st.markdown("<h4 style='color:#E2E8F0;'>⏱️ Average dwell by vessel</h4>", unsafe_allow_html=True)
    if len(_closed):
        _dwell = (_closed.groupby("reactor_name")["hours_in_reactor"].mean()
                  .reset_index().sort_values("hours_in_reactor", ascending=True))
        fig_dwell = px.bar(_dwell, x="hours_in_reactor", y="reactor_name", orientation="h")
        fig_dwell.update_traces(marker_color=_C_DWELL, marker_line_color="#7DD3FC",
                                marker_line_width=1, opacity=0.85)
        fig_dwell.update_layout(**_CHART_LAYOUT)
        fig_dwell.update_xaxes(title="Hours")
        fig_dwell.update_yaxes(title="")
        st.plotly_chart(fig_dwell, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("No emptied fillings in this window yet.")

with chart2:
    st.markdown("<h4 style='color:#E2E8F0;'>🧪 QC turnaround trend</h4>", unsafe_allow_html=True)
    if len(_done):
        _trend = _done.copy()
        _trend["day"] = _trend["qc_result_at"].dt.date
        _trend = _trend.groupby("day")["hours_at_qc"].mean().reset_index()
        fig_qc = px.area(_trend, x="day", y="hours_at_qc", markers=True)
        fig_qc.update_traces(
            line=dict(color=_C_QC, width=3),
            marker=dict(size=7, color="#FFFFFF", line=dict(width=2, color=_C_QC)),
            fillcolor="rgba(56, 189, 248, 0.12)")
        fig_qc.update_layout(**_CHART_LAYOUT)
        fig_qc.update_yaxes(title="Hours")
        fig_qc.update_xaxes(title="")
        st.plotly_chart(fig_qc, use_container_width=True, config={"displayModeBar": False})
    else:
        st.caption("No completed QC round trips in this window yet.")

st.markdown("---")

# The one that gets somebody out of their chair: what is waiting right now,
# oldest first. A count of things waiting is a statistic; a list with an age
# against each is a job.
if len(_at_qc):
    st.markdown("#### 🧪 Out at QC now")
    for _, b in _at_qc.sort_values("hours_at_qc", ascending=False).iterrows():
        _h = b["hours_at_qc"]
        _tone = _C_BAD if _h and _h > 48 else _C_WARN if _h and _h > 24 else _C_QC
        st.markdown(
            f'<div style="background:linear-gradient(180deg, #0D1627 0%, #080D1A 100%); '
            f'border-left:4px solid {_tone}; border-radius:8px; padding:10px 14px; '
            f'margin-bottom:8px; display:flex; justify-content:space-between; '
            f'align-items:center;">'
            f'<div><b style="color:#FFFFFF;">{esc(b["reactor_name"])}</b> '
            f'<span style="color:#94A3B8;">· {esc(b["resin_type"] or "resin not recorded")}</span></div>'
            f'<div style="color:{_tone}; font-weight:800;">{_h:,.0f} h at QC</div>'
            f'</div>', unsafe_allow_html=True)

if len(_open):
    _no_qc = _open[(_open["qc_result"] == "") & (~_open["qc_open"])]
    if len(_no_qc):
        st.caption(f"⚠️ {len(_no_qc)} filling(s) in a vessel with no QC recorded "
                   f"at all. That is a blank, not a pass.")

st.markdown("---")

# --------------------------------------------------------------- QC entry --
# Moved here from Live Reactors: one screen for the report and the entry
# that feeds it, rather than a trip to the reactor page for "and such."
if can("manage_qc"):
    st.markdown("#### 💾 Record QC")

    _row_by_id = {int(r["id"]): r for r in rows}
    _id_options = sorted(_row_by_id, key=lambda i: _row_by_id[i]["filled_at"] or datetime.min,
                         reverse=True)

    def _batch_label(bid: int) -> str:
        b = _row_by_id[bid]
        _stamp = b["filled_at"].strftime("%d %b %H:%M") if b["filled_at"] else "unknown start"
        _flag = (" · no QC yet" if not b["qc_sent_at"] and not b["qc_result"]
                 else " · at QC" if b["qc_open"] else "")
        return f'{b["reactor_name"]} — {b["resin_type"] or "resin not recorded"} ({_stamp}){_flag}'

    _batch_id = st.selectbox("Which filling", _id_options, format_func=_batch_label)
    _current = _row_by_id[_batch_id]

    with st.container(border=True):
        _now = datetime.now()
        _qc_col1, _qc_col2 = st.columns(2)
        with _qc_col1:
            _sent_on = st.date_input(
                "Sample sent", value=(_current["qc_sent_at"] or _now).date(),
                key=f"bh_qc_sd_{_batch_id}")
            _sent_at = st.time_input(
                "at", value=(_current["qc_sent_at"] or _now).time(),
                key=f"bh_qc_st_{_batch_id}")
        with _qc_col2:
            _has_result = st.checkbox(
                "The result has come back",
                value=bool(_current["qc_result_at"]),
                key=f"bh_qc_has_{_batch_id}")
            _res_on = _res_at = None
            if _has_result:
                _res_on = st.date_input(
                    "Result received", value=(_current["qc_result_at"] or _now).date(),
                    key=f"bh_qc_rd_{_batch_id}")
                _res_at = st.time_input(
                    "at ", value=(_current["qc_result_at"] or _now).time(),
                    key=f"bh_qc_rt_{_batch_id}")

        _result = ""
        if _has_result:
            _result = st.radio(
                "Result", ("pass", "hold", "fail"),
                index=("pass", "hold", "fail").index(_current["qc_result"] or "pass"),
                horizontal=True, key=f"bh_qc_r_{_batch_id}")

        _note = st.text_input("Note (optional)", value=_current["qc_note"],
                              max_chars=200, key=f"bh_qc_n_{_batch_id}")
        st.caption(
            "Times are typed rather than stamped, because the result usually "
            "arrives before anybody is at a screen. Put in when it actually "
            "happened.")
        if st.button("💾 Save QC", key=f"bh_qc_save_{_batch_id}", use_container_width=True):
            _ok, _msg = set_batch_qc(
                _batch_id,
                sent_at=datetime.combine(_sent_on, _sent_at),
                result_at=(datetime.combine(_res_on, _res_at) if _has_result else None),
                result=_result if _has_result else "",
                note=_note,
                by=st.session_state.get("user_name", ""))
            st.toast(("✅ " if _ok else "❌ ") + _msg)
            if _ok:
                st.rerun()
        if _current.get("qc_by"):
            st.caption(f"Last recorded by {esc(_current['qc_by'])}.")

    st.markdown("---")

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
    "Times in a vessel come from an operator marking the tank empty, or from "
    "the next changeover confirmed at the pump if nobody did - whichever "
    "happens first. QC times are entered above, so they are only as good as "
    "when somebody enters them - which is worth saying before anybody "
    "averages them.")
