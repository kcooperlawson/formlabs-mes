"""Every theme, every component, and an automated readability check.

Two things this exists to prevent.

**A component that was only styled in some themes.** Each hand-written theme
carries its own copy of about fifteen CSS rules, so a new card or badge has
to be added to every one of them, and a miss is invisible until somebody
happens to be using that theme. This app has already been bitten by exactly
that shape of bug - a page that raised only after a theme change. Rendering
the whole component set in one place turns "somebody will notice eventually"
into one glance.

**Text nobody can read.** Colour choices that look fine to whoever picked
them can fall below the contrast floor, and on a floor terminal under plant
lighting that is the difference between a number being read and being
guessed. The check below is arithmetic, not opinion: WCAG's contrast ratio,
with 4.5:1 the accepted floor for body text. It found two real failures on
first run, one of them in the default theme.
"""
import os
import re
import sys

import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if os.path.dirname(os.path.abspath(__file__)) not in sys.path:
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from database import do_logout, esc
from theme_engine import contrast_ratio
from resin_palette import resin_chip, delta_e, resin_pattern, resin_family

st.set_page_config(page_title="Theme Gallery | Formlabs MES", page_icon="🎨", layout="wide")

try:
    from themes import THEMES, PALETTES
except ImportError:
    THEMES, PALETTES = {"Default Dark": "<style></style>"}, {}
st.markdown(THEMES.get(st.session_state.get("preferred_theme", "Default Dark"),
                       list(THEMES.values())[0]), unsafe_allow_html=True)

if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") not in ["manager", "admin"]:
    st.error("🔒 Access Denied: Restricted to Plant Management.")
    st.stop()

from ui_shell import render_shell
cookie_manager = render_shell()

st.subheader("🎨 Theme Gallery & Readability Check")
st.caption("What every component looks like, and whether anyone can actually read it.")

AA_BODY = 4.5      # WCAG AA floor for normal text
AA_LARGE = 3.0     # ...and for large or bold text

tab_check, tab_components, tab_palettes = st.tabs(
    ["✅ Readability check", "🧩 Components", "🎨 Palettes"])


# --------------------------------------------------------------- the check --
def _first(pattern, css, *groups):
    m = re.search(pattern, css)
    if not m:
        return None
    for g in groups or (1,):
        if m.group(g):
            return m.group(g)
    return None


def audit(css: str) -> dict:
    """Pull the colour pairs that carry text out of a theme's stylesheet.

    Reads the generated CSS rather than a palette object so it works on the
    hand-written themes too - which is the point, since those are the ones
    nobody can check by eye across twenty-four variants.
    """
    out = {}
    app = re.search(r"\.stApp\s*\{([^}]*)\}", css)
    if app:
        bg = _first(r"background-color:\s*(#[0-9A-Fa-f]{3,6})", app.group(1))
        fg = _first(r"(?<!-)color:\s*(#[0-9A-Fa-f]{3,6})", app.group(1))
        if bg and fg:
            out["Body text on page"] = (fg, bg)
    card_bg = _first(
        r"\.telemetry-grid-card\s*\{[^}]*background:\s*(?:linear-gradient\([^)]*?(#[0-9A-Fa-f]{6})|(#[0-9A-Fa-f]{3,6}))",
        css, 1, 2)
    if card_bg:
        lab = _first(r"\.telemetry-label\s*\{[^}]*color:\s*(#[0-9A-Fa-f]{3,6})", css)
        val = _first(r"\.telemetry-val-large\s*\{[^}]*color:\s*(#[0-9A-Fa-f]{3,6})", css)
        if lab:
            out["Card label"] = (lab, card_bg)
        if val:
            out["Card value"] = (val, card_bg)
    return out


with tab_check:
    st.markdown("Contrast ratio of each text colour against what sits behind it. "
                f"**{AA_BODY}:1** is the WCAG AA floor for body text; large bold "
                f"figures are held to **{AA_LARGE}:1**.")

    rows, skipped = [], []
    for name, css in THEMES.items():
        pairs = audit(css)
        if not pairs:
            skipped.append(name)
            continue
        row = {"Theme": name, "Kind": "generated" if name in PALETTES else "hand-written"}
        worst, worst_where = 99.0, ""
        for label, (fg, bg) in pairs.items():
            r = contrast_ratio(fg, bg)
            row[label] = round(r, 1)
            floor = AA_LARGE if label == "Card value" else AA_BODY
            if r / floor < worst / (AA_LARGE if worst_where == "Card value" else AA_BODY):
                worst, worst_where = r, label
        row["Verdict"] = "✅ passes" if all(
            contrast_ratio(*pairs[l]) >= (AA_LARGE if l == "Card value" else AA_BODY)
            for l in pairs) else "⚠️ below AA"
        rows.append(row)

    df = pd.DataFrame(rows)
    failing = df[df["Verdict"] != "✅ passes"] if not df.empty else pd.DataFrame()

    c1, c2, c3 = st.columns(3)
    c1.metric("Themes checked", len(df))
    c2.metric("Below AA", len(failing),
              delta="none" if failing.empty else f"{len(failing)} to fix",
              delta_color="normal" if failing.empty else "inverse")
    c3.metric("Light themes", sum(1 for p in PALETTES.values() if p.light),
              help="None of the original twenty-four were light.")

    if failing.empty:
        st.success("Every theme's text clears the contrast floor against its own background.")
    else:
        st.warning("These themes have text below the readable floor:")
        st.dataframe(failing, hide_index=True, use_container_width=True)

    st.dataframe(df.sort_values("Theme"), hide_index=True, use_container_width=True)
    if skipped:
        st.caption("Not machine-checkable (gradient or non-hex backgrounds), so these "
                   "still need a human eye: " + ", ".join(f"**{esc(s)}**" for s in skipped))


# ---------------------------------------------------------- component demo --
with tab_components:
    st.caption("Every shared component, in the theme you currently have selected. "
               "Switch theme in Account & Preferences and come back — anything that "
               "vanishes or turns unreadable is a theme missing a rule.")

    st.markdown("##### Telemetry cards")
    cols = st.columns(4)
    for col, (label, value) in zip(cols, [("UNITS POURED", "12,480"), ("YIELD", "99.4%"),
                                          ("DOWNTIME", "42 min"), ("ACTIVE RUNS", "3")]):
        col.markdown(
            f'<div class="telemetry-grid-card"><div class="telemetry-label">{esc(label)}</div>'
            f'<div class="telemetry-val-large">{esc(value)}</div></div>',
            unsafe_allow_html=True)

    st.markdown("<br>##### Brand header and badge", unsafe_allow_html=True)
    st.markdown(
        '<div class="brand-header"><div><b>Formlabs MES</b>'
        '<span class="system-badge">Live</span></div><div>Shift 1</div></div>',
        unsafe_allow_html=True)

    st.markdown("##### Resin chips — colour plus texture")
    st.caption("The texture is the point: several of these colours are within a "
               "perceptual distance of 5, which is the same colour to the eye. "
               "Families that look alike must never wear the same pattern.")
    demo = ["Clear V4", "Rigid 4000 V1", "Rigid 10K V1", "Grey Pro V1", "Tough 2000 V1",
            "Black V4", "Tough 1500 V1", "High Temp V2", "Castable Wax V1", "ESD V1"]
    st.markdown(
        " ".join(resin_chip(r, size="lg") for r in demo), unsafe_allow_html=True)
    st.markdown("Without texture, for comparison:")
    st.markdown(
        " ".join(resin_chip(r, size="lg", pattern=False) for r in demo),
        unsafe_allow_html=True)

    st.markdown("<br>##### Inputs, buttons and tabs", unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    b1.text_input("Text input", value="L-2411A0742", key="gal_text")
    b2.number_input("Number input", value=1110.0, step=1.0, key="gal_num")
    b3.selectbox("Select", ["Pump 1", "Pump 2"], key="gal_sel")
    d1, d2, d3 = st.columns(3)
    d1.button("Primary action", type="primary", use_container_width=True, key="gal_b1")
    d2.button("Secondary", use_container_width=True, key="gal_b2")
    d3.download_button("Download", data="x", file_name="x.txt",
                       use_container_width=True, key="gal_b3")

    st.markdown("##### Status messages")
    st.success("Lot matches this run.")
    st.warning("Weight is above the high limit.")
    st.error("STOP — do not pour.")
    st.info("No readings recorded yet.")


# ------------------------------------------------------------- the palettes --
with tab_palettes:
    if not PALETTES:
        st.info("No generated themes are registered.")
    else:
        st.caption("Generated themes are defined as a palette rather than as CSS, "
                   "so a new component is styled once for all of them.")
        for name, p in PALETTES.items():
            swatches = "".join(
                f'<span title="{esc(role)} {esc(col)}" style="display:inline-block;width:34px;'
                f'height:34px;background:{esc(col)};border:1px solid rgba(128,128,128,.5);'
                f'border-radius:5px;margin-right:5px;"></span>'
                for role, col in (("ground", p.ground), ("surface", p.surface),
                                  ("raised", p.raised), ("line", p.line), ("ink", p.ink),
                                  ("body", p.body), ("muted", p.muted),
                                  ("accent", p.accent), ("accent 2", p.accent_2)))
            tags = " ".join(f"`{esc(t)}`" for t in p.tags)
            st.markdown(f"**{esc(name)}** &nbsp; {tags}<br>{swatches}", unsafe_allow_html=True)
            st.caption(f"body {contrast_ratio(p.body, p.ground):.1f}:1 · "
                       f"headings {contrast_ratio(p.ink, p.ground):.1f}:1 · "
                       f"secondary {contrast_ratio(p.muted, p.ground):.1f}:1 · "
                       f"button label {contrast_ratio(p.ground, p.accent):.1f}:1")
