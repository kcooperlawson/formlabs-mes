
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from database import get_lot_verifications_df, LOT_PHOTO_DIR, do_logout

st.set_page_config(page_title="Lot Verification | Formlabs MES", page_icon="🔒", layout="wide")
from database import esc
from components import empty_state
from database import get_all_resin_specs_df
from resin_palette import resin_chip, stored_color_map, style_resin_column


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
_check_auth(_stx.CookieManager(key="auth_lot_verification"))

if not st.session_state.get("authenticated", False) or not can("view_manager_cockpit"):
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

# ===================== UNIVERSAL NAVIGATION & SIDEBAR =====================
from ui_shell import render_shell
cookie_manager = render_shell()
current_role = st.session_state.get("user_role", "operator")

st.subheader("🔒 Cartridge Lot Verification")
st.caption("Every lot check completed at a pouring station. The passes are what prove the check "
           "actually happened; the flags are the mix-ups this gate exists to catch.")

win = st.selectbox("Window", (7, 14, 30, 90), index=2,
                   format_func=lambda d: f"Last {d} days", key="lv_window")
df = get_lot_verifications_df(days=win)
_resin_colours = stored_color_map(get_all_resin_specs_df("ALL"))

if df.empty:
    st.info("No lot checks recorded in this window yet. Checks start appearing as soon as "
            "operators log pouring on V1, V2 or Pigment.")
    st.stop()

# Timestamps are stored in UTC (datetime.utcnow); the floor reads local time.
df["timestamp"] = (pd.to_datetime(df["timestamp"])
                   .dt.tz_localize("UTC").dt.tz_convert("America/New_York"))
flagged = df[df["result"].isin(["mismatch", "expired", "rejected"])]
full_checks = df[df["check_level"] == "full"]
fast_checks = df[df["check_level"] == "fast"]
catches = df[df["result"] == "rejected"]

k1, k2, k3, k4, k5 = st.columns(5)
with k1:
    st.metric("Checks logged", f"{len(df):,}")
with k2:
    pct_full = (len(full_checks) / len(df) * 100) if len(df) else 0
    st.metric("Full checks", f"{len(full_checks):,}", delta=f"{pct_full:.0f}% of all checks")
with k3:
    st.metric("Flagged", f"{len(flagged):,}",
              delta="Review needed" if len(flagged) else "All clear",
              delta_color="inverse" if len(flagged) else "normal")
with k4:
    st.metric("Cartridges pulled", f"{len(catches):,}", help="Caught before pouring — the saves.")
with k5:
    rate = (len(flagged) / len(df) * 100) if len(df) else 0
    st.metric("Flag rate", f"{rate:.1f}%", help="Share of checks that didn't come back clean.")

st.markdown("---")

tab_flag, tab_cov, tab_all = st.tabs(
    ("⛔ Flagged Checks", "📊 Coverage by Operator", "🗂️ Every Check"))

# ---------------------------------------------------------------- FLAGGED --
with tab_flag:
    if flagged.empty:
        st.success("✅ No mismatched, expired or pulled cartridges in this window.")
    else:
        st.caption("Each of these is either a mix-up that reached the pour or one an operator "
                   "stopped. Both are worth reading.")
        for _, row in flagged.iterrows():
            tone = {"mismatch": "#EF4444", "expired": "#F59E0B", "rejected": "#38BDF8"}.get(row["result"], "#94A3B8")
            headline = {"mismatch": "LOT MISMATCH — poured anyway",
                        "expired": "EXPIRED LOT — poured anyway",
                        "rejected": "CARTRIDGE PULLED — nothing poured"}.get(row["result"], row["result"].upper())
            with st.container():
                _resin_html = (
                    resin_chip(row["resin_type"], _resin_colours.get(str(row["resin_type"])))
                    if row["resin_type"] else
                    "<span style='color:#64748B; font-size:0.85rem;'>no resin recorded</span>"
                )
                st.markdown(
                    f"<div style='border-left:4px solid {tone}; border-radius:6px; padding:10px 14px; "
                    f"background-color:#0F172A; margin-bottom:6px;'>"
                    f"<b style='color:{tone};'>● {headline}</b>"
                    f"<span style='float:right; color:#94A3B8; font-size:0.8rem;'>"
                    f"{row['timestamp'].strftime('%b %d, %I:%M %p')}</span><br>"
                    f"<span style='color:#E2E8F0; font-size:0.85rem;'>"
                    f"{esc(row['operator_name'])} · {esc(row['pump_station'])} · {esc(row['cartridge_type'])} · "
                    f"</span>{_resin_html}</div>",
                    unsafe_allow_html=True)
                st.markdown(
                    f"**Run expected:** `{row['expected_lot'] or '—'}`  \n"
                    f"**Cartridge read:** `{row['entered_lot'] or '—'}`")
                st.markdown(f"*{row['reason'] or 'No reason recorded.'}*")
                if pd.notna(row["production_log_id"]):
                    st.caption(f"Production log #{int(row['production_log_id'])} carries this flag.")
                else:
                    st.caption("No production logged against this check \u2014 the container was "
                               "pulled before pouring, which is the outcome this control is for.")
                # Historic checks may still carry a photo from before capture was
                # removed; show it when one exists rather than losing the evidence.
                if row["photo_filename"]:
                    img_path = os.path.join(LOT_PHOTO_DIR, str(row["photo_filename"]))
                    if os.path.exists(img_path):
                        st.image(img_path, width=340, caption="Lot label as photographed")
                st.markdown("---")

# --------------------------------------------------------------- COVERAGE --
with tab_cov:
    st.caption("A station showing almost no full checks is a station taking the one-tap path every "
               "hour — the gate is only as good as the reading behind it.")
    by_op = df.groupby("operator_name").agg(
        checks=("id", "count"),
        full=("check_level", lambda s: int((s == "full").sum())),
        fast=("check_level", lambda s: int((s == "fast").sum())),
        flags=("result", lambda s: int(s.isin(["mismatch", "expired", "rejected"]).sum())),
    ).reset_index()
    by_op["% full"] = (by_op["full"] / by_op["checks"] * 100).round(0)
    by_op = by_op.sort_values("checks", ascending=False)
    st.dataframe(by_op.rename(columns={"operator_name": "Operator", "checks": "Checks",
                                       "full": "Full", "fast": "One-tap", "flags": "Flagged"}),
                 use_container_width=True, hide_index=True)

    st.markdown("##### By station")
    by_station = df.groupby("pump_station").agg(
        checks=("id", "count"),
        flags=("result", lambda s: int(s.isin(["mismatch", "expired", "rejected"]).sum())),
    ).reset_index().sort_values("flags", ascending=False)
    st.dataframe(by_station.rename(columns={"pump_station": "Station", "checks": "Checks",
                                            "flags": "Flagged"}),
                 use_container_width=True, hide_index=True)

# -------------------------------------------------------------- EVERYTHING --
with tab_all:
    st.dataframe(
        df[["timestamp", "operator_name", "pump_station", "cartridge_type", "resin_type",
            "expected_lot", "entered_lot", "result", "check_level",
            "reason", "production_log_id"]]
        .rename(columns={"timestamp": "When", "operator_name": "Operator",
                         "pump_station": "Station", "cartridge_type": "Format",
                         "resin_type": "Resin", "expected_lot": "Run lot",
                         "entered_lot": "Cartridge lot",
                         "result": "Result", "check_level": "Level", "reason": "Reason",
                         "production_log_id": "Log #"})
        .pipe(style_resin_column, "Resin", _resin_colours),
        use_container_width=True, hide_index=True)
    st.download_button("⬇️ Export this window as CSV",
                       data=df.to_csv(index=False).encode("utf-8"),
                       file_name=f"lot_verifications_last_{win}_days.csv",
                       mime="text/csv", use_container_width=True)
