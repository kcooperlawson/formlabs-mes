"""Colour identity for resin formulations.

Every place the app names a resin, it should also show that resin's colour.
On the floor people recognise a formulation by the colour of its label long
before they read the words on it, and the master spreadsheet the plant has
always worked from is colour-coded that way already. A screen that prints
"Grey V4.1" in the same grey text as everything else is asking an operator
to read carefully at exactly the moment they are moving fast.

Where a colour comes from, in order:

1. **What the manager set.** `resin_specs.color_tag` holds an explicit
   override, editable in Resin Canvas. If it holds a real colour, that wins,
   always. Nothing below can override a human decision.

2. **The known palette** (`_PALETTE`). Sampled directly from the plant's own
   colour-coded resin sheet, so what the app shows matches what people
   already have in front of them rather than inventing a second scheme.

3. **The family rules** (`_FAMILY_RULES`). This is the part that answers
   "what happens when someone adds a resin nobody listed a colour for".
   Formlabs names resins by family and revision - Black V4, Black V4.1,
   Black V5 - so a name is matched on its family, and a new revision
   inherits its family's colour automatically the day it is added. Add
   "Black V6" tomorrow and it is the right grey-black immediately, with
   nobody editing anything.

4. **A hash of the name.** Only reached by something that matches no family
   at all - a genuinely new material, or a custom formulation. The name is
   hashed onto one of forty prepared swatches, so it is stable (the same
   name is always the same colour, on every machine and after every
   restart), clearly distinct from its neighbours, and still looks like it
   belongs to the set. Then a manager can override it if they care.

The point of 3 and 4 together is that there is no such thing as an
uncoloured resin on screen, and no step anyone has to remember to perform
when a resin is added.

Deliberately free of any Streamlit or database import: this module is pure
functions over a name and an optional stored value, so it can be used by the
pages, by the Alembic migration that backfills the column, and by the tests,
without dragging any of those into each other.
"""
from __future__ import annotations

import hashlib
import html
import re

# ---------------------------------------------------------------------------
# Legacy compatibility.
#
# Before colours were a real feature, `resin_specs.color_tag` defaulted to the
# Formlabs Forge accent for every row, so a database that predates migration
# 0005 has this same value on all of them - identical, and therefore useless as
# a per-resin colour. Treat it as "nothing was ever chosen here" so those rows
# fall through to the palette rather than rendering as one wall of orange.
#
# Migration 0005 replaces it with a real per-resin value, after which this only
# matters for a database that has not been upgraded yet.
# ---------------------------------------------------------------------------
_LEGACY_PLACEHOLDER = "#EA580C"

_HEX_RE = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")

# Exact names, sampled from the plant's colour-coded resin sheet.
_PALETTE = {
    "black v4": "#3B3C3C",
    "black v4.1": "#3B3C3C",
    "black v5": "#3B3C3C",
    "clear v4": "#EBF5FA",
    "clear v4.1": "#EBF5FA",
    "clear v5": "#EBF5FA",
    "model v2": "#F5CBA6",
    "model v3": "#F5CBA6",
    "durable v2": "#F6DB6F",
    "draft v2": "#5C6D7D",
    "flexible 80a v1": "#1ABC9C",
    "flexible 80a wck": "#1ABC9C",
    "grey pro v1": "#545454",
    "grey v4": "#666B6D",
    "grey v4.1": "#666B6D",
    "grey v5": "#666B6D",
    "rigid 10k v1": "#F1F5FE",
    "rigid 4000 v1": "#F1FAFE",
    "tough 1500 v1": "#424548",
    "tough 2000 v1": "#53585B",
    "white v4": "#E9E8CC",
    "white v4.1": "#E9E8CC",
    "white v5": "#E9E8CC",
    "color base v1": "#E6E6FA",
    "high temp v2": "#E67D21",
    "castable wax v1": "#6B3382",
    "castable wax 40 v1": "#D1B4DE",
    "flame retardant v1": "#BF382A",
    "esd v1": "#F29C12",
    "silicone 40a v1": "#A2E3D6",
    "elastic 50a v2": "#9A58B5",
    "alumina 4n v1": "#FDECEC",
    "clear cast v1": "#A8CCE3",
    "fast model v1": "#818277",
}

# Family rules, checked in order - most specific first, because these are
# substring matches and "clear cast" also contains "clear", "grey pro" also
# contains "grey", and "fast model" also contains "model". Getting this order
# wrong is silent and looks like a colour that is merely a bit off, so the
# tests assert each of the overlapping pairs explicitly.
_FAMILY_RULES = (
    ("castable wax 40", "#D1B4DE"),
    ("castable wax", "#6B3382"),
    ("flame retardant", "#BF382A"),
    ("high temp", "#E67D21"),
    ("color base", "#E6E6FA"),
    ("colour base", "#E6E6FA"),
    ("clear cast", "#A8CCE3"),
    ("grey pro", "#545454"),
    ("gray pro", "#545454"),
    ("rigid 10k", "#F1F5FE"),
    ("rigid", "#F1FAFE"),
    ("tough 2000", "#53585B"),
    ("tough 1500", "#424548"),
    ("tough", "#424548"),
    ("fast model", "#818277"),
    ("flexible", "#1ABC9C"),
    ("silicone", "#A2E3D6"),
    ("elastic", "#9A58B5"),
    ("alumina", "#FDECEC"),
    ("esd", "#F29C12"),
    ("draft", "#5C6D7D"),
    ("durable", "#F6DB6F"),
    ("model", "#F5CBA6"),
    ("black", "#3B3C3C"),
    ("white", "#E9E8CC"),
    ("grey", "#666B6D"),
    ("gray", "#666B6D"),
    ("clear", "#EBF5FA"),
)

_FALLBACK = "#9AA3AE"

# Text colours for chips. Near-black rather than pure black, so a chip on a
# pale background does not read as harder-edged than the rest of the page.
_DARK_TEXT = "#111827"
_LIGHT_TEXT = "#FFFFFF"


def _norm(name) -> str:
    """Lower-case, collapse whitespace, drop punctuation that varies by typist."""
    s = str(name or "").strip().lower()
    s = s.replace("_", " ").replace("-", " ")
    s = re.sub(r"[^a-z0-9. ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _is_real_colour(value) -> bool:
    if not value:
        return False
    v = str(value).strip()
    if not _HEX_RE.match(v):
        return False
    return v.upper() != _LEGACY_PLACEHOLDER


def _expand(hex_colour: str) -> str:
    """Normalise #abc to #AABBCC."""
    v = str(hex_colour).strip().upper()
    if len(v) == 4:
        return "#" + "".join(c * 2 for c in v[1:])
    return v


def _rgb(hex_colour: str):
    v = _expand(hex_colour)
    return int(v[1:3], 16), int(v[3:5], 16), int(v[5:7], 16)


def _hsl_to_hex(h: float, s: float, ll: float) -> str:
    c = (1 - abs(2 * ll - 1)) * s
    x = c * (1 - abs(((h / 60.0) % 2) - 1))
    m = ll - c / 2
    r, g, b = {
        0: (c, x, 0.0), 1: (x, c, 0.0), 2: (0.0, c, x),
        3: (0.0, x, c), 4: (x, 0.0, c), 5: (c, 0.0, x),
    }[int(h // 60) % 6]
    return "#%02X%02X%02X" % (
        round((r + m) * 255), round((g + m) * 255), round((b + m) * 255)
    )


# Hues for the fallback swatches, deliberately ordered so that consecutive
# entries sit on opposite sides of the colour wheel. A plain `hue = hash % 360`
# looks correct and is not: two unrelated names landing 8 degrees apart produce
# two colours nobody can tell apart, which is worse than no colour at all
# because it implies a relationship that isn't there. Stepping the list means
# neighbouring indices are always obviously different.
_FALLBACK_HUES = (
    0, 180, 60, 240, 120, 300, 30, 210, 90, 270,
    150, 330, 15, 195, 75, 255, 135, 315, 45, 225,
)
_FALLBACK_SWATCHES = tuple(
    _hsl_to_hex(h, s, l)
    for l, s in ((0.80, 0.48), (0.64, 0.42))
    for h in _FALLBACK_HUES
)


def _hash_colour(name: str) -> str:
    """A stable swatch derived from the name itself.

    md5 rather than Python's hash(): hash() is randomised per process, which
    would give the same resin a different colour on every app restart - the
    one thing a colour code must never do. The same name gives the same
    swatch on every machine, forever.
    """
    digest = hashlib.md5(_norm(name).encode("utf-8")).hexdigest()
    return _FALLBACK_SWATCHES[int(digest[:8], 16) % len(_FALLBACK_SWATCHES)]


def _luminance(hex_colour: str) -> float:
    """WCAG relative luminance, used to decide black or white text."""
    def chan(v):
        v = v / 255.0
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (chan(v) for v in _rgb(hex_colour))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _shade(hex_colour: str, factor: float) -> str:
    """Lighten (factor > 0) or darken (factor < 0) toward white/black."""
    r, g, b = _rgb(hex_colour)
    if factor >= 0:
        r, g, b = (v + (255 - v) * factor for v in (r, g, b))
    else:
        r, g, b = (v * (1 + factor) for v in (r, g, b))
    return "#%02X%02X%02X" % (round(r), round(g), round(b))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def resin_color(name, stored=None) -> str:
    """The background colour for a resin, as #RRGGBB. Never returns None."""
    if _is_real_colour(stored):
        return _expand(stored)

    key = _norm(name)
    if not key:
        return _FALLBACK

    if key in _PALETTE:
        return _PALETTE[key]

    for needle, colour in _FAMILY_RULES:
        if needle in key:
            return colour

    return _hash_colour(key)


def resin_text_color(background: str) -> str:
    """Black or white, whichever is readable on the given background."""
    return _LIGHT_TEXT if _luminance(background) < 0.45 else _DARK_TEXT


def resin_colors(name, stored=None):
    """(background, text, border) for a resin.

    The border matters more than it sounds: several of these colours are a
    few percent off white, and without an edge a chip on a light theme is an
    invisible rectangle with text floating in it.
    """
    bg = resin_color(name, stored)
    fg = resin_text_color(bg)
    border = _shade(bg, -0.18) if _luminance(bg) > 0.6 else _shade(bg, 0.16)
    return bg, fg, border


def resin_chip(name, stored=None, *, bold: bool = True, size: str = "md",
               title: str = None) -> str:
    """A coloured pill containing the resin's name, as an HTML string.

    Escaped here rather than at the call site, so a resin name containing a
    '<' cannot break the card it renders in and no caller has to remember.
    Intended for st.markdown(..., unsafe_allow_html=True).
    """
    label = str(name or "").strip()
    if not label:
        return ""
    bg, fg, border = resin_colors(label, stored)
    pad, font = {
        "sm": ("1px 7px", "0.72rem"),
        "md": ("2px 10px", "0.82rem"),
        "lg": ("4px 14px", "0.95rem"),
    }.get(size, ("2px 10px", "0.82rem"))
    return (
        f'<span title="{html.escape(title or label)}" style="'
        f"display:inline-block;background:{bg};color:{fg};"
        f"border:1px solid {border};border-radius:999px;padding:{pad};"
        f"font-size:{font};font-weight:{600 if bold else 500};"
        f"line-height:1.45;white-space:nowrap;vertical-align:middle;"
        f'">{html.escape(label)}</span>'
    )


def resin_dot(name, stored=None, *, text: bool = True) -> str:
    """A small colour dot, optionally followed by the name.

    For dense rows where a full pill would crowd everything else out.
    """
    label = str(name or "").strip()
    if not label:
        return ""
    bg, _fg, border = resin_colors(label, stored)
    dot = (
        f'<span style="display:inline-block;width:10px;height:10px;'
        f"border-radius:50%;background:{bg};border:1px solid {border};"
        f'margin-right:6px;vertical-align:-1px;"></span>'
    )
    return dot + html.escape(label) if text else dot


def resin_color_map(names, stored_map=None) -> dict:
    """{name: colour} for charts, so a resin is the same colour everywhere.

    A donut of output by formulation that picks its own palette teaches a
    second, conflicting colour language for the same set of things.
    """
    stored_map = stored_map or {}
    out = {}
    for n in names:
        if n is None:
            continue
        key = str(n)
        out[key] = resin_color(key, stored_map.get(key) or stored_map.get(_norm(key)))
    return out


def stored_color_map(specs_df) -> dict:
    """Pull {resin_name: color_tag} out of a resin specs dataframe.

    Tolerates a missing column or an empty frame, so a caller can hand over
    whatever it already has without guarding first.
    """
    try:
        if specs_df is None or getattr(specs_df, "empty", True):
            return {}
        if "resin_name" not in specs_df.columns or "color_tag" not in specs_df.columns:
            return {}
        return {
            str(r): c
            for r, c in zip(specs_df["resin_name"], specs_df["color_tag"])
            if r is not None
        }
    except Exception:
        return {}


def style_resin_column(df, column: str = "resin_name", stored_map=None):
    """Tint one column of a dataframe by resin, for st.dataframe.

    Returns a pandas Styler. Falls back to returning the frame untouched if
    the column is missing, so a display list that changes shape degrades to
    an uncoloured table rather than taking the page down.
    """
    if df is None or getattr(df, "empty", True) or column not in getattr(df, "columns", []):
        return df
    stored_map = stored_map or {}

    def _cell(value):
        bg = resin_color(value, stored_map.get(str(value)))
        return f"background-color: {bg}; color: {resin_text_color(bg)}; font-weight: 600;"

    try:
        return df.style.map(_cell, subset=[column])
    except AttributeError:
        # pandas < 2.1 spells it applymap
        return df.style.applymap(_cell, subset=[column])
