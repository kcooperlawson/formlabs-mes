"""My Shift Summary tab - an opt-in, end-of-shift personal stats breakdown.

Built for operators and packers to see, on demand, how their day went:
units poured/packed, scrap, quality yield, logs submitted, and a couple of
charts. Gated behind an explicit button rather than computed on every page
load - this is a "check it when I want it" screen, not one more thing
competing for attention while someone is mid-pour. A fragment, so tapping
that button (or hiding the summary again) only reruns this tab, not the
whole page underneath it.

Nothing here is written anywhere - it is read-only, generated fresh from
today's already-submitted logs each time it is opened.
"""
from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st

from components import empty_state
from database import get_production_logs_df
from resin_palette import resin_color_map

# Same dark, transparent-background chart theme Analytics_Hub.py already
# uses for every other chart in this app - so this tab doesn't introduce a
# second visual language for the same kind of number.
_CHART_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#94A3B8", family="sans-serif"),
    margin=dict(t=40, b=20, l=10, r=10),
    xaxis=dict(showgrid=False, zeroline=False),
    yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.05)", zeroline=False),
)

# The hourly-timeline chart has exactly one series (this operator, today),
# so per the categorical-color rule it is a plain accent rather than an
# entry in a multi-series identity scheme - nothing here needs a legend.
_ACCENT = "#00D2FF"

_SHOW_KEY = "shift_summary_shown"


@st.fragment
def render(ctx):
    current_user = ctx.current_user
    current_role = ctx.current_role

    st.markdown("#### 📊 My Shift Summary")

    if not st.session_state.get(_SHOW_KEY, False):
        st.caption("A personal breakdown of today's numbers, generated on demand. "
                   "Nothing is saved or sent anywhere - it's built fresh from what "
                   "you've already logged today.")
        if st.button("📊 View My Shift Summary", use_container_width=True, type="primary",
                     key="summary_show_btn"):
            st.session_state[_SHOW_KEY] = True
            st.rerun()
        return

    _top = st.columns((5, 1))
    _top[0].caption("Today so far - tap again any time, the numbers just refresh.")
    if _top[1].button("Hide", use_container_width=True, key="summary_hide_btn"):
        st.session_state[_SHOW_KEY] = False
        st.rerun()

    today = date.today()
    df_today = get_production_logs_df(start_date=today, end_date=today, operator=current_user)

    if df_today.empty:
        empty_state("Nothing logged yet today",
                    "Come back once you've poured, packed, or logged something and "
                    "this will fill in.", icon="📭")
        return

    log_type_wanted = "Packing Count" if current_role == "packer" else "Hourly Bottle Count"
    df_mine = df_today[df_today["log_type"] == log_type_wanted].copy()

    units = int(df_mine["bottles_filled"].sum()) if not df_mine.empty else 0
    scrap = int(df_mine["scrap_empty"].sum() + df_mine["scrap_filled"].sum()) if not df_mine.empty else 0
    yield_pct = (units / (units + scrap) * 100) if (units + scrap) > 0 else 100.0
    logs_submitted = int(len(df_today))

    if current_role == "packer":
        c1, c2 = st.columns(2)
        c1.metric("📦 Units Packed", f"{units:,}")
        c2.metric("📝 Logs Submitted", f"{logs_submitted:,}")
    else:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("🧪 Units Poured", f"{units:,}")
        c2.metric("🗑️ Scrap Units", f"{scrap:,}")
        c3.metric("✅ Quality Yield", f"{yield_pct:.1f}%")
        c4.metric("📝 Logs Submitted", f"{logs_submitted:,}")

    st.markdown("<br>", unsafe_allow_html=True)

    if df_mine.empty:
        empty_state(f"No {'packing' if current_role == 'packer' else 'pouring'} logs yet today",
                    "The chart below fills in once you've submitted at least one log.",
                    icon="📭")
        return

    chart1, chart2 = st.columns((3, 2))

    with chart1:
        st.markdown("##### ⏱️ Hourly Timeline")
        _hourly = df_mine.copy()
        _hourly["hour"] = pd.to_datetime(_hourly["timestamp"]).dt.floor("h")
        _hourly = _hourly.groupby("hour", as_index=False)["bottles_filled"].sum().sort_values("hour")
        fig_line = px.bar(_hourly, x="hour", y="bottles_filled")
        # Thin bars, one consistent accent, no legend needed for one series -
        # the section heading above already names what this is.
        fig_line.update_traces(
            marker_color=_ACCENT,
            marker_line_width=0,
            width=1000 * 60 * 40,  # ~40 real minutes wide, in the ms a date-axis bar width wants
            hovertemplate="%{x|%H:%M} — %{y} units<extra></extra>",
        )
        fig_line.update_xaxes(title="", tickformat="%H:%M")
        fig_line.update_yaxes(title="Units")
        fig_line.update_layout(**_CHART_LAYOUT)
        st.plotly_chart(fig_line, use_container_width=True, config={"displayModeBar": False})

    with chart2:
        st.markdown("##### 🧪 By Formulation")
        _by_resin = df_mine.groupby("resin_type", as_index=False)["bottles_filled"].sum()
        _by_resin = _by_resin[_by_resin["bottles_filled"] > 0]
        if _by_resin.empty:
            st.caption("No formulation breakdown available yet.")
        else:
            # Same colours as everywhere else a resin is named in this app -
            # a slice is identifiable without reading the legend.
            _colours = resin_color_map(_by_resin["resin_type"].tolist(), ctx.resin_colour_map)
            fig_donut = px.pie(_by_resin, names="resin_type", values="bottles_filled", hole=0.7,
                               color="resin_type", color_discrete_map=_colours)
            fig_donut.update_traces(
                hoverinfo="label+percent",
                textinfo="none",
                marker=dict(line=dict(color="#02040A", width=2)),
            )
            fig_donut.update_layout(
                **_CHART_LAYOUT,
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.3, xanchor="center", x=0.5),
            )
            fig_donut.add_annotation(text=f"<b>{units:,}</b><br>Total", x=0.5, y=0.5, font_size=18,
                                     showarrow=False, font_color="#FFFFFF")
            st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})
