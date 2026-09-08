"""Build a theme's CSS from a palette instead of writing it by hand.

The original twenty-four themes are each about fifteen hand-written CSS rules
with the colours typed in literally. That works, and they look good, but it
has two costs that were starting to bite:

  * A new component has to be styled twenty-four times, and one miss shows up
    only when somebody happens to be on that theme. The app has already been
    bitten by exactly that - a page that raised only after a theme change.
  * Every theme is dark. Not one of the twenty-four is light, which is a real
    gap on a bright pouring floor where a dark screen is a mirror, and it
    showed up again when the handbook had to be printed.

So: describe a theme as a Palette - about a dozen colours and three style
choices - and generate the CSS. A new component is then styled once and every
generated theme gets it. A light theme is a palette rather than a rewrite.

Deliberately additive. The existing twenty-four are left exactly as they are:
people have theme preferences saved against them by name, they are somebody's
design work, and rewriting them to prove a point would risk twenty-four
regressions to gain tidiness. New themes are generated; old ones are kept.
The two live side by side in one dictionary and nothing downstream can tell
which is which.

There is one thing generation must fix that hand-writing never had to. The
shared BASE_UI_CSS paints navigation pills with `rgba(255,255,255,0.05)` and
pins tab labels to slate and white - safe assumptions when every theme was
dark, and invisible white-on-white when one is not. A light palette therefore
emits a correction block after the base CSS. That block exists because the
base stylesheet assumes a dark ground, and it should be deleted the day that
assumption is removed from BASE_UI_CSS itself.
"""
from __future__ import annotations

import textwrap
from dataclasses import dataclass, field

SANS = '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif'
MONO = '"JetBrains Mono", "Cascadia Code", Consolas, "Courier New", monospace'
SERIF = 'Georgia, "Iowan Old Style", "Palatino Linotype", serif'


@dataclass
class Palette:
    """Everything one theme needs to know about itself.

    Kept small on purpose. Every additional knob is a decision each new theme
    has to make, and a dozen colours plus a few shape choices is enough to
    make themes that look genuinely different from one another.
    """
    name: str
    ground: str                      # page background
    surface: str                     # cards, sidebar
    raised: str                      # hover / elevated
    line: str                        # borders
    ink: str                         # headings and primary text
    body: str                        # body text
    muted: str                       # secondary text
    accent: str                      # primary action
    accent_2: str                    # hover / highlight
    good: str = "#22C55E"
    warn: str = "#F59E0B"
    bad: str = "#EF4444"
    light: bool = False              # is the ground lighter than the ink?
    font: str = SANS
    radius: str = "8px"
    glow: bool = False               # neon-style outer glows
    upper_buttons: bool = True
    header_bg: str = ""              # defaults to surface
    tags: tuple = field(default_factory=tuple)   # for the gallery: "light", "high-contrast", ...


def _rgba(hex_colour: str, alpha: float) -> str:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def _relative_luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    def chan(v):
        v = int(v, 16) / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(h[i:i + 2]) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast_ratio(fg: str, bg: str) -> float:
    """WCAG contrast ratio. 4.5 is the floor for body text, 3.0 for large."""
    a, b = _relative_luminance(fg), _relative_luminance(bg)
    lo, hi = sorted((a, b))
    return (hi + 0.05) / (lo + 0.05)


def _css(block: str) -> str:
    """Strip the indentation off a generated stylesheet before it is emitted.

    Not cosmetic. These strings are handed to st.markdown(unsafe_allow_html),
    and CommonMark treats a four-space-indented line as a code block - so an
    indented <style> appended after other content renders as visible source
    on the page instead of being applied. That is exactly what happened to
    the light-mode corrections: they showed up as a grey box of CSS text at
    the top of every light theme.
    """
    return textwrap.dedent(block).strip()


def _light_mode_fixes(p: Palette) -> str:
    """Undo the dark-ground assumptions baked into BASE_UI_CSS.

    Emitted only for light palettes. See the module docstring: the base
    stylesheet paints nav pills in translucent white and pins tab labels to
    slate and white, which are invisible on a pale ground.
    """
    return _css(f"""
    <style>
        /* --- light-mode corrections to BASE_UI_CSS --- */
        .stPageLink a {{
            background-color: {_rgba(p.ink, 0.05)} !important;
            border: 1px solid {_rgba(p.ink, 0.12)} !important;
            color: {p.body} !important;
        }}
        .stPageLink a:hover {{
            background-color: {_rgba(p.accent, 0.14)} !important;
            border-color: {p.accent} !important;
        }}
        /* The popover trigger gets the same translucent pill as the nav links
           in the base stylesheet, so it needs the same correction here - a
           white-on-white wash otherwise. */
        [data-testid="stPopover"] button {{
            background-color: {_rgba(p.ink, 0.05)} !important;
            border: 1px solid {_rgba(p.ink, 0.12)} !important;
        }}
        [data-testid="stPopover"] button,
        [data-testid="stPopover"] button * {{
            color: {p.body} !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab"] {{
            background-color: {_rgba(p.ink, 0.04)} !important;
            border: 1px solid {_rgba(p.ink, 0.10)} !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {{
            background-color: {_rgba(p.accent, 0.16)} !important;
            border: 1px solid {p.accent} !important;
            box-shadow: none !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab"] p {{
            color: {p.muted} !important;
        }}
        div[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] p {{
            color: {p.ink} !important;
            text-shadow: none !important;
        }}
    </style>
    """)


def build(p: Palette) -> str:
    """The full stylesheet for one palette."""
    header_bg = p.header_bg or p.surface
    glow_btn = (f"box-shadow: 0 0 12px {_rgba(p.accent, 0.55)} !important;"
                if p.glow else
                f"box-shadow: 0 2px 6px {_rgba('#000000', 0.25 if not p.light else 0.10)} !important;")
    glow_hover = (f"box-shadow: 0 0 22px {_rgba(p.accent_2, 0.85)} !important;"
                  if p.glow else
                  f"box-shadow: 0 4px 12px {_rgba(p.accent, 0.35)} !important;")
    upper = ("text-transform: uppercase; letter-spacing: 0.1em;"
             if p.upper_buttons else "letter-spacing: 0.01em;")

    return _css(f"""
    <style>
        /* One type scale and one spacing step, for every theme.
           These grew page by page as raw HTML in f-strings, so sizes and
           paddings drifted a few pixels between screens. Nobody can name what
           is wrong with that; they just feel it, and what it reads as is
           software somebody assembled rather than software somebody bought.
           Five sizes, two weights, one 8px step. Anything new takes a token
           rather than inventing a number. */
        :root {{
            --mes-t-xs: 0.72rem;   /* eyebrow labels, all caps */
            --mes-t-sm: 0.86rem;   /* captions, secondary lines */
            --mes-t-md: 1rem;      /* body */
            --mes-t-lg: 1.35rem;   /* card headings, secondary figures */
            --mes-t-xl: 1.75rem;   /* the number a card exists to show */
            --mes-w-mid: 600;
            --mes-w-strong: 800;
            --mes-sp-1: 8px;
            --mes-sp-2: 16px;
            --mes-sp-3: 24px;
            /* And one rhythm for movement. Fast is feedback - a hover, a
               button. Slow is a value actually changing. Two durations and
               one curve is what makes motion read as designed instead of as
               several people's defaults sitting next to each other. */
            --mes-fast: 160ms;
            --mes-slow: 900ms;
            --mes-ease: cubic-bezier(0.22, 0.61, 0.36, 1);
        }}

        .stApp {{ background-color: {p.ground} !important; color: {p.body} !important;
                  font-family: {p.font} !important; }}
        header[data-testid="stHeader"] {{ background: transparent !important; }}

        .brand-header {{ display: flex; align-items: center; justify-content: space-between;
            padding: var(--mes-sp-2) var(--mes-sp-3); background: {header_bg};
            border: 1px solid {p.line};
            border-radius: {p.radius}; margin-bottom: var(--mes-sp-2);
            border-bottom: 3px solid {p.accent};
            box-shadow: 0 4px 10px {_rgba('#000000', 0.10 if p.light else 0.35)}; }}
        .system-badge {{ background: {_rgba(p.accent, 0.15)}; color: {p.accent};
            font-size: var(--mes-t-xs); font-weight: var(--mes-w-strong);
            letter-spacing: 0.15em; padding: 4px 10px;
            border-radius: 4px; border: 1px solid {p.accent}; text-transform: uppercase;
            margin-left: 14px; }}

        .telemetry-grid-card {{ background: {p.surface}; border: 1px solid {p.line};
            border-radius: {p.radius}; padding: var(--mes-sp-1) var(--mes-sp-2);
            min-height: 96px;
            transition: all var(--mes-fast) var(--mes-ease);
            border-left: 4px solid {p.muted}; }}
        .telemetry-grid-card:hover {{ transform: translateX(4px);
            border-left: 4px solid {p.accent}; background: {p.raised};
            box-shadow: -4px 4px 10px {_rgba('#000000', 0.08 if p.light else 0.40)}; }}
        .telemetry-label {{ font-size: var(--mes-t-xs); font-weight: var(--mes-w-strong); letter-spacing: 0.12em;
            color: {p.muted}; text-transform: uppercase; }}
        .telemetry-val-large {{ font-size: var(--mes-t-xl); font-weight: var(--mes-w-strong); color: {p.ink};
            line-height: 1.2; }}

        .stTextInput > div > div > input {{ background-color: {p.surface} !important;
            color: {p.ink} !important; border: 1px solid {p.line} !important;
            border-radius: {p.radius} !important; font-weight: var(--mes-w-mid); }}
        .stTextInput > div > div > input:focus {{ border-color: {p.accent} !important;
            box-shadow: 0 0 0 2px {_rgba(p.accent, 0.25)} !important; }}

        .stButton>button {{ background: {p.accent} !important; color: {p.ground} !important;
            font-weight: var(--mes-w-strong) !important; border: none !important;
            border-radius: {p.radius} !important; {glow_btn}
            transition: all var(--mes-fast) var(--mes-ease) !important; {upper} }}
        .stButton>button:hover {{ background: {p.accent_2} !important; {glow_hover} }}

        .filter-section-card {{ background: {p.surface}; border: 1px solid {p.line};
            border-radius: {p.radius}; padding: var(--mes-sp-2); margin: var(--mes-sp-2) 0; }}

        [data-testid="stSidebar"] {{ background-color: {p.surface} !important;
            border-right: 1px solid {p.line} !important; }}
        [data-testid="stSidebarNav"] {{ padding-top: 1.5rem; }}
        [data-testid="stSidebarNav"] a {{ color: {p.muted} !important; font-weight: var(--mes-w-mid) !important;
            border-radius: {p.radius} !important; margin: 4px var(--mes-sp-2) !important;
            transition: all var(--mes-fast) var(--mes-ease) !important; }}
        [data-testid="stSidebarNav"] a:hover {{ background-color: {p.raised} !important;
            color: {p.accent} !important; transform: translateX(5px) !important; }}
        [data-testid="stSidebarNav"] a[aria-current="page"] {{ background: {p.accent} !important;
            color: {p.ground} !important; font-weight: var(--mes-w-strong) !important; }}

        h1, h2, h3, h4, h5, h6 {{ color: {p.ink} !important; }}
        hr {{ border-color: {p.line} !important; }}
        code {{ color: {p.accent_2} !important; background: {_rgba(p.ink, 0.07)} !important; }}
    </style>
    """)
