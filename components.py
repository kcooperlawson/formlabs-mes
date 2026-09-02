"""Shared UI pieces, so a card looks the same on every screen.

Three things this fixes.

**The same markup was written out by hand in a dozen places.** Cards, stat
tiles, notes and section headers are all built from raw HTML in f-strings,
copied from page to page and drifting a little each time. That is the same
shape of duplication that put a 131-line navigation block into eleven files
and hid a crash in eight of them - and it means a styling fix has to be made
once per copy, or it isn't really made.

**Escaping had to be remembered at every call site.** These blocks render
with unsafe_allow_html and interpolate database values that people on the
floor typed. Escaping inside the component means a note containing a '<'
cannot break the card it sits in, and no future caller has to know that.

**Empty screens said nothing.** Most pages render blank, or a bare "No
assigned runs currently active." A screen with no data yet is the first
thing a new starter sees, and the difference between a tool that looks
finished and one that looks broken is whether it says what happens next.
`empty_state` exists to make the useful version the easy one to write.

Deliberately plain functions returning HTML strings, or thin wrappers over
st.markdown - not a widget framework. Every page here already knows how to
render markdown, and the goal is one definition per component, not a new
abstraction to learn.
"""
from __future__ import annotations

import html

import streamlit as st


def esc(value) -> str:
    """Escape a value on its way into markup. None becomes an empty string."""
    return html.escape("" if value is None else str(value))


# --------------------------------------------------------------- empty state --
def empty_state(title: str, body: str = "", *, icon: str = "📭",
                action: str = "", tone: str = "neutral") -> None:
    """What a screen says when it has nothing to show yet.

    `body` should say what will make the emptiness go away - "runs appear
    here once a manager dispatches one" - rather than restating the absence.
    `action` is the concrete next step, if there is one the reader can take.

    Deliberately not an error or a warning: having no data yet is a normal
    state on a system that was installed last week, and painting it red
    teaches people to ignore red.
    """
    edge = {"neutral": "rgba(148,163,184,0.55)",
            "good": "#22C55E", "warn": "#F59E0B"}.get(tone, "rgba(148,163,184,0.55)")
    action_html = (
        f'<div style="margin-top:8px;font-size:0.87rem;opacity:0.95;">'
        f'<b>Next:</b> {esc(action)}</div>' if action else "")
    st.markdown(
        f'<div style="border:1px dashed {edge};border-radius:10px;'
        f'padding:18px 20px;margin:6px 0 14px;opacity:0.92;">'
        f'<div style="font-size:1.05rem;font-weight:700;">{icon} {esc(title)}</div>'
        f'<div style="margin-top:6px;font-size:0.9rem;line-height:1.5;opacity:0.85;">'
        f'{esc(body)}</div>{action_html}</div>',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------- containers --
def section_header(title: str, eyebrow: str = "", caption: str = "") -> None:
    """A titled section divider, consistent across pages."""
    if eyebrow:
        st.markdown(
            f'<div style="font-size:0.7rem;font-weight:800;letter-spacing:0.14em;'
            f'text-transform:uppercase;opacity:0.65;">{esc(eyebrow)}</div>',
            unsafe_allow_html=True)
    st.markdown(f"#### {esc(title)}")
    if caption:
        st.caption(caption)


def card(title: str = "", body: str = "", *, tag: str = "",
         accent: str = "", render: bool = True) -> str:
    """A bordered panel. Returns the HTML so it can be composed, and renders
    it by default so the common case is one line."""
    bar = f"border-left:3px solid {accent};" if accent else ""
    tag_html = (f'<div style="font-size:0.66rem;font-weight:800;letter-spacing:0.1em;'
                f'text-transform:uppercase;opacity:0.7;margin-bottom:5px;">{esc(tag)}</div>'
                if tag else "")
    title_html = (f'<div style="font-weight:700;font-size:0.95rem;margin-bottom:3px;">'
                  f'{esc(title)}</div>' if title else "")
    out = (f'<div class="filter-section-card" style="{bar}">'
           f'{tag_html}{title_html}'
           f'<div style="font-size:0.88rem;line-height:1.5;opacity:0.85;">{esc(body)}</div>'
           f'</div>')
    if render:
        st.markdown(out, unsafe_allow_html=True)
    return out


def stat(value, label: str, *, sub: str = "", render: bool = True) -> str:
    """One telemetry figure, styled by whichever theme is active.

    Uses the theme's own .telemetry-* classes rather than inline colours, so
    a stat tile follows the palette instead of fighting it.
    """
    sub_html = (f'<div style="font-size:0.72rem;opacity:0.7;margin-top:3px;">{esc(sub)}</div>'
                if sub else "")
    out = (f'<div class="telemetry-grid-card">'
           f'<div class="telemetry-label">{esc(label)}</div>'
           f'<div class="telemetry-val-large">{esc(value)}</div>{sub_html}</div>')
    if render:
        st.markdown(out, unsafe_allow_html=True)
    return out


def note(body: str, *, eyebrow: str = "", tone: str = "info") -> None:
    """A short aside - a design decision, a caveat, a reminder."""
    edge = {"info": "rgba(148,163,184,0.6)", "warn": "#F59E0B",
            "good": "#22C55E", "bad": "#EF4444"}.get(tone, "rgba(148,163,184,0.6)")
    eyebrow_html = (f'<div style="font-size:0.66rem;font-weight:800;letter-spacing:0.12em;'
                    f'text-transform:uppercase;opacity:0.7;margin-bottom:4px;">'
                    f'{esc(eyebrow)}</div>' if eyebrow else "")
    st.markdown(
        f'<div style="border-left:3px solid {edge};padding:10px 14px;margin:4px 0 12px;'
        f'background:rgba(128,128,128,0.06);border-radius:0 6px 6px 0;">'
        f'{eyebrow_html}<div style="font-size:0.89rem;line-height:1.5;">{esc(body)}</div></div>',
        unsafe_allow_html=True)


# ------------------------------------------------------------- save feedback --
def save_state(status: str, message: str = "") -> None:
    """Say plainly whether a write reached the database.

    On this plant's network - which drops in parts of the building - "did
    that submit?" is a real question, and a page that silently re-runs
    answers it badly. An operator who is unsure re-submits, and a duplicated
    hourly count is worse than a missing one because nothing looks wrong.

    Three states, deliberately: in flight, landed, and failed with what to do
    about it.
    """
    if status == "saving":
        st.markdown(
            '<div style="font-size:0.9rem;opacity:0.85;">⏳ Saving…</div>',
            unsafe_allow_html=True)
    elif status == "saved":
        st.markdown(
            f'<div style="font-size:0.9rem;color:#22C55E;font-weight:600;">'
            f'✅ Saved{(" — " + esc(message)) if message else ""}</div>',
            unsafe_allow_html=True)
    elif status == "failed":
        st.error(
            f"❌ Not saved{(' — ' + message) if message else ''}. "
            "Nothing was recorded, so nothing is duplicated — check the connection "
            "and submit again."
        )
