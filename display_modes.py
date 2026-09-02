"""Two adjustments to how the interface renders, for how it is actually used.

Neither changes a colour scheme - they ride on top of whatever theme is
selected, so every one of the thirty-four keeps working.

**Glove mode.** Operators handling resin wear nitrile. Capacitive touch still
registers through it, but precision drops sharply, and the pouring form asks
people to hit number steppers and a lot field with a gloved fingertip. This
pushes every interactive target to a size a gloved hand can actually land on
and scales the type with it. It is a toggle rather than a default because a
manager at a desk with a mouse wants the density back.

The 48px floor is not arbitrary: it is the long-standing touch-target
guidance in both the WCAG and platform accessibility literature, and it
happens to be about the contact patch of a gloved fingertip.

**Night dimming.** The second shift runs into the night. A screen calibrated
for a bright morning bay is punishing at 2am, and the fix people reach for
otherwise is turning the monitor down, which loses the colour coding the lot
check and the resin chips depend on. A modest brightness and warmth reduction
keeps the hues intact while taking the glare off.

Driven from the plant's own configured shift times rather than a hardcoded
hour, because "night" here means "not the day shift" - a local fact this app
already stores.

Both are pure CSS strings. Nothing here touches the database or Streamlit.
"""
from __future__ import annotations

import textwrap

# Comfortably above the 44-48px touch-target floor, with room for a border.
GLOVE_TARGET_PX = 52


def glove_css(scale: float = 1.15) -> str:
    """Bigger hit targets and type, for gloved hands on a floor terminal."""
    t = GLOVE_TARGET_PX
    return textwrap.dedent(f"""
    <style>
        /* --- glove mode --- */
        .stButton > button,
        .stDownloadButton > button,
        [data-testid="stFormSubmitButton"] > button {{
            min-height: {t}px !important;
            font-size: {0.95 * scale:.2f}rem !important;
            padding-top: 0.55rem !important; padding-bottom: 0.55rem !important;
        }}
        .stTextInput input, .stNumberInput input, .stDateInput input,
        [data-baseweb="select"] > div {{
            min-height: {t}px !important;
            font-size: {1.0 * scale:.2f}rem !important;
        }}
        /* The +/- steppers on a number input are the smallest targets on the
           pouring form and the ones most often hit with a glove on. */
        .stNumberInput button {{
            min-width: {t - 8}px !important; min-height: {t - 8}px !important;
        }}
        [data-testid="stCheckbox"] label, [data-testid="stRadio"] label {{
            min-height: {t - 10}px !important;
            font-size: {0.95 * scale:.2f}rem !important;
            display: flex !important; align-items: center !important;
        }}
        [data-testid="stCheckbox"] label span:first-child,
        [data-testid="stRadio"] label span:first-child {{
            transform: scale({1.0 + (scale - 1) * 2.4:.2f});
            transform-origin: left center;
            margin-right: 0.6rem !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab"] {{
            min-height: {t}px !important; padding: 0 1.1rem !important;
        }}
        [data-testid="stPageLink-NavLink"] {{ min-height: {t - 6}px !important; }}
        label, .stMarkdown p {{ font-size: {0.95 * scale:.2f}rem !important; }}
    </style>
    """).strip()


def night_css(strength: float = 1.0) -> str:
    """Take the glare off a screen being read in the dark.

    A filter on the app container rather than new colours, so it composes
    with all thirty-four themes and cannot break one of them. Deliberately
    gentle: enough to stop a dark room feeling lit by the monitor, not so
    much that the reds and greens the lot check relies on shift into each
    other. Never applied to images, so a stamp photograph under review is
    still judged at its true colour.
    """
    s = max(0.0, min(float(strength), 1.0))
    brightness = 1.0 - 0.12 * s
    sepia = 0.10 * s
    return textwrap.dedent(f"""
    <style>
        /* --- night dimming --- */
        [data-testid="stAppViewContainer"], [data-testid="stSidebar"] {{
            filter: brightness({brightness:.3f}) sepia({sepia:.3f});
        }}
        /* A photograph being reviewed has to keep its real colours. */
        [data-testid="stAppViewContainer"] img,
        [data-testid="stImage"] img {{
            filter: brightness({1 / brightness:.3f}) sepia(0);
        }}
    </style>
    """).strip()


def display_css(*, glove: bool = False, night: bool = False,
                night_strength: float = 1.0) -> str:
    """Whatever adjustments are active, as one string. Empty when neither is."""
    out = []
    if glove:
        out.append(glove_css())
    if night:
        out.append(night_css(night_strength))
    return "".join(out)
