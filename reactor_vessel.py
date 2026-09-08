"""Drawing the supply vessels as the things they actually are.

The reactor page used to draw every tank as a rounded rectangle with a
capacity-picked corner radius, and called the 5,000 L one a "cone bottom on a
heavy metal stand". None of that is what is out on the floor. What is out
there is three genuinely different kinds of vessel:

Every fabricated vessel here is the same shape: bolted top flange, a barrel,
a dark band at the joint, a cone bottom and a steel frame under it. Only the
totes are flat-bottomed. So there is one drawing for the fabricated vessels
with two sets of proportions, rather than two drawings that could drift
apart.

  bulk_vertical  Tall and narrow - M-205 and the White V5 beside it - with
                 litre graduations running up the barrel: 200 through 4,400,
                 marked every 200. Those graduations are how somebody
                 standing at the vessel reads its level, so they are drawn
                 here too, and the liquid surface lands on the same mark it
                 would land on out there. That is the whole point of the
                 picture: two people, one at the screen and one at the
                 vessel, should be looking at the same thing and be able to
                 say so.

  cone_mixer     Short and wide - M-101 - with ribs down the cone and no
                 painted scale, because the real one has none: two
                 hand-written marks near the rim and nothing more. The
                 proportions alone tell it apart from the tall one across a
                 room.

  ibc_tote       Not a fabricated vessel at all: a translucent bottle in a
                 moulded cage on a pallet, flat bottomed, with a ball valve
                 at the front bottom corner. Roughly 1,000 L. It reads
                 completely differently from the other two and should.

The liquid takes the resin's own colour rather than a fixed blue, for the
same reason the chips do: on the floor a formulation is recognised by its
colour before its name is read. Two things follow from that and are handled
below - a very dark resin still has to be visibly a liquid against a dark
page, and the percentage printed over it has to stay readable whatever colour
it is sitting on. Neither is left to luck; see `_readable_ink` and
`_lift`.

Deliberately free of any Streamlit or database import. This is a function
from a handful of numbers to a string of SVG, which means it can be checked
without a browser, without a server and without a database - and vessel
geometry is exactly the kind of thing that is easy to get quietly wrong and
hard to notice by eye.
"""
from __future__ import annotations

import html

# The vessel kinds, in the order a manager should see them offered.
VESSEL_TYPES = ("bulk_vertical", "cone_mixer", "ibc_tote")

VESSEL_LABELS = {
    "bulk_vertical": "Tall bulk reactor",
    "cone_mixer": "Squat cone mixer",
    "ibc_tote": "IBC tote",
}

VESSEL_HELP = {
    "bulk_vertical": "Tall and narrow, cone bottom, litre marks up the barrel (M-205)",
    "cone_mixer": "Short and wide, cone bottom, ribs, no painted scale (M-101)",
    "ibc_tote": "Caged bottle on a pallet, flat bottomed, ball valve (around 1,000 L)",
}

# Where the capacity bands fall when nobody has said what a vessel is. These
# are a starting point for a new tank, not a rule the drawing re-derives:
# migration 0011 seeds the column from exactly these numbers and the manager
# corrects whatever they got wrong.
BULK_FROM_L = 3500
CONE_FROM_L = 1500

# Everything below is drawn in this box and scaled by the browser, so one set
# of coordinates serves the reactor wall, a phone and the floor display.
VIEW_W, VIEW_H = 240, 400

_LOW_LEVEL_PCT = 10.0
_LOW_LEVEL_COLOUR = "#EF4444"
_STEEL = "#94A3B8"
_STEEL_DARK = "#475569"
_FRAME = "#334155"
# The vessels out there are off-white polyethylene, and drawing them that way
# was the first thing tried. It does not work: White V5 is a real resin in
# this fleet and a pale liquid inside a pale shell has no level at all. So the
# empty part of a vessel is dark and the liquid is the resin's own colour,
# which is the one arrangement where every resin the plant runs is legible.
# What carries "this is M-101 and not M-205" is the outline, the flange, the
# cone, the frame and the cage - the shape, not the fill.
_SHELL = "#0B111E"
_SHELL_EDGE = "#9FB0C9"
_TICK = "#64748B"
_TICK_INK = "#94A3B8"
_INK_LIGHT = "#FFFFFF"
_INK_DARK = "#0B1220"


def default_vessel_type(capacity_l) -> str:
    """The kind a vessel probably is, from its capacity alone.

    Used for a tank nobody has classified yet, and by the migration that
    seeds the column. Right for most of a fleet and wrong for the interesting
    ones, which is why it is a default and not the answer.
    """
    try:
        litres = float(capacity_l or 0)
    except (TypeError, ValueError):
        litres = 0.0
    if litres >= BULK_FROM_L:
        return "bulk_vertical"
    if litres >= CONE_FROM_L:
        return "cone_mixer"
    return "ibc_tote"


def resolve_vessel_type(stored, capacity_l) -> str:
    """What was set, if it is a kind we can draw; otherwise the capacity's guess."""
    kind = str(stored or "").strip().lower()
    return kind if kind in VESSEL_TYPES else default_vessel_type(capacity_l)


# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------

def _rgb(colour: str):
    c = str(colour or "").strip().lstrip("#")
    if len(c) == 3:
        c = "".join(ch * 2 for ch in c)
    if len(c) != 6:
        return None
    try:
        return int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except ValueError:
        return None


def _luminance(colour: str) -> float:
    """0 for black, 1 for white. Perceptual weights, not a plain average."""
    parts = _rgb(colour)
    if parts is None:
        return 0.5
    r, g, b = parts
    return (0.2126 * r + 0.7152 * g + 0.0722 * b) / 255.0


def _readable_ink(colour: str) -> str:
    """Black or white text, whichever survives on this background.

    The percentage is printed over the liquid, and the liquid is now whatever
    colour the resin is. White V5 and Black V5 are both real, both in the
    fleet, and a fixed ink colour is unreadable on one of them.
    """
    return _INK_DARK if _luminance(colour) > 0.55 else _INK_LIGHT


def _lift(colour: str, amount: float) -> str:
    """Move a colour towards white by `amount` (0-1)."""
    parts = _rgb(colour)
    if parts is None:
        return colour
    r, g, b = (int(round(v + (255 - v) * amount)) for v in parts)
    return f"#{r:02X}{g:02X}{b:02X}"


def _liquid_colours(resin_colour: str, low: bool):
    """Top and bottom of the liquid, and the ink that goes over it.

    A near-black resin drawn flat black against a near-black page is a hole,
    not a level, so the floor of the gradient is lifted until the liquid is
    unmistakably a liquid. Nothing is lifted so far that Black stops reading
    as black - the point is still that you can tell the tanks apart by colour
    from across the room.
    """
    if low:
        return _LOW_LEVEL_COLOUR, "#F87171", _INK_LIGHT
    base = str(resin_colour or "").strip() or "#3B82F6"
    if _rgb(base) is None:
        base = "#3B82F6"
    if _luminance(base) < 0.16:
        base = _lift(base, 0.28)
    return base, _lift(base, 0.34), _readable_ink(base)


# ---------------------------------------------------------------------------
# Graduations
# ---------------------------------------------------------------------------

def _tick_step(capacity_l: float):
    """Litres between marks, and between numbered marks.

    The real tanks are marked every 200 L and numbered at every one of them,
    which works at arm's length on a 12-foot vessel and turns into a grey
    smear at 200 pixels. So the marks stay at the vessel's own spacing and
    only every fifth carries a number.
    """
    if capacity_l >= 3000:
        return 200.0, 1000.0
    if capacity_l >= 1200:
        return 100.0, 500.0
    return 50.0, 200.0


def _graduations(capacity_l: float, x_from: float, x_to: float,
                 y_top: float, y_bottom: float, numbered_x: float,
                 from_litres: float = 0.0) -> str:
    """Litre marks up the barrel of a vessel, bottom to top.

    `from_litres` is what is already below the bottom of the marked section -
    on a cone-bottomed vessel, everything the cone holds. The marks span the
    barrel, so the litres they represent start where the barrel does, which
    is why the lowest mark on the real tank is not zero.
    """
    if capacity_l <= from_litres:
        return ""
    step, label_step = _tick_step(capacity_l)
    span = y_bottom - y_top
    marked = capacity_l - from_litres
    out = []
    litres = step * (int(from_litres // step) + 1)
    while litres < capacity_l:
        y = y_bottom - span * ((litres - from_litres) / marked)
        numbered = abs((litres / label_step) - round(litres / label_step)) < 1e-9
        length = (x_to - x_from) * (1.0 if numbered else 0.55)
        w = 2.6 if numbered else 2.0
        out.append(
            f'<line x1="{x_from:.1f}" y1="{y:.1f}" x2="{x_from + length:.1f}" y2="{y:.1f}" '
            f'stroke="#000000" stroke-width="{w:.1f}" opacity="0.45"/>'
            f'<line x1="{x_from:.1f}" y1="{y:.1f}" x2="{x_from + length:.1f}" y2="{y:.1f}" '
            f'stroke="{_TICK_INK}" stroke-width="{w - 1.1:.1f}" '
            f'opacity="{0.95 if numbered else 0.6}"/>')
        if numbered:
            out.append(
                f'<text x="{numbered_x:.1f}" y="{y + 3.0:.1f}" text-anchor="end" '
                f'font-size="9" font-weight="600" fill="{_TICK_INK}">'
                f'{int(round(litres)):,}</text>')
        litres += step
    return "".join(out)


# ---------------------------------------------------------------------------
# The vessels
# ---------------------------------------------------------------------------

# How a level moves to its new height rather than jumping to it. A transition
# on a plain value, never an animation: the pages carrying these re-run on a
# timer, so it has to glide when the litres actually change and sit perfectly
# still when they do not. A browser that will not transition an SVG geometry
# attribute snaps to the new level, which is what this did before.
_EASE = ("transition:y 0.9s ease-in-out, height 0.9s ease-in-out, "
         "cy 0.9s ease-in-out;")


def _surface(x: float, w: float, y: float, uid: str, flat: bool = False) -> str:
    """The top of the liquid, drawn as a surface rather than a cut edge.

    A vessel is a round thing seen from slightly above, so its contents end in
    an ellipse, not a straight line. Drawing that line straight is what made
    these read as bar charts with a tank around them. The ellipse costs two
    shapes: the liquid's own colour bowing up at the back, and a paler ring on
    top of it where the light catches the surface.

    A tote is a square bottle, so it gets a flat surface and the highlight
    alone. Giving it the same ellipse would be drawing a cylinder that is not
    there.
    """
    ry = 0.0 if flat else max(3.0, w * 0.075)
    cx = x + w / 2
    body = "" if flat else (
        f'<ellipse cx="{cx:.1f}" cy="{y:.1f}" rx="{w / 2:.1f}" ry="{ry:.1f}" '
        f'fill="url(#lvl{uid})" style="{_EASE}"/>')
    return (
        body
        + f'<ellipse cx="{cx:.1f}" cy="{y:.1f}" rx="{w / 2 - 1:.1f}" '
          f'ry="{max(1.6, ry * 0.72):.1f}" fill="#FFFFFF" opacity="0.30" '
          f'style="{_EASE}"/>'
        + f'<ellipse cx="{cx:.1f}" cy="{y:.1f}" rx="{w / 2 - 1:.1f}" '
          f'ry="{max(1.1, ry * 0.72):.1f}" fill="none" stroke="#FFFFFF" '
          f'stroke-width="1.4" opacity="0.65" style="{_EASE}"/>')


def _sheen(x: float, w: float, y_top: float, h: float) -> str:
    """A soft highlight down one side, so the liquid reads as wet.

    Kept to one band on the left at low opacity. Anything stronger starts
    competing with the resin's own colour, and the colour is the thing this
    picture is recognised by from across the floor.
    """
    return (f'<rect x="{x + w * 0.10:.1f}" y="{y_top:.1f}" '
            f'width="{max(4.0, w * 0.13):.1f}" height="{max(0.0, h):.1f}" '
            f'rx="3" fill="#FFFFFF" opacity="0.10" style="{_EASE}"/>')


def _percent_label(x: float, y: float, pct: float, ink: str, idle: bool = False) -> str:
    """The number over the liquid - or IDLE, on a vessel with nothing on it.

    A tank with no resin assigned is not 0.0% full of anything; printing a
    percentage there invites somebody to go and look for a leak.
    """
    text, size = ("IDLE", 18) if idle else (f"{pct:.1f}%", 26)
    return (f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="middle" font-size="{size}" '
            f'font-weight="800" fill="{ink}" letter-spacing="{"0.12em" if idle else "0"}" '
            f'style="paint-order:stroke; stroke:rgba(0,0,0,0.45); stroke-width:3px;">'
            f'{text}</text>')


def _tag_plate(cx: float, y: float, text: str, w: float = 76.0) -> str:
    """The stencilled asset tag, drawn the way it is stuck on the vessel."""
    if not text:
        return ""
    return (f'<rect x="{cx - w / 2:.1f}" y="{y:.1f}" width="{w:.1f}" height="15" rx="2" '
            f'fill="#0F172A"/>'
            f'<text x="{cx:.1f}" y="{y + 11.2:.1f}" text-anchor="middle" font-size="10" '
            f'font-weight="700" fill="#F8FAFC" letter-spacing="0.05em">{html.escape(text)}</text>')


def _bay_bollard(x: float, y_top: float, y_bottom: float, marker: str) -> str:
    """The black post beside the vessel with its orange bay marker.

    Every vessel out there has one and it is how a bay is named in
    conversation, so it is drawn where it stands rather than printed as a
    caption somewhere else.
    """
    post = (f'<rect x="{x:.1f}" y="{y_top:.1f}" width="13" height="{y_bottom - y_top:.1f}" '
            f'rx="6" fill="#111827" stroke="#0B1220" stroke-width="0.5"/>')
    if not marker:
        return post
    label = html.escape(marker.strip().upper()[:2])
    cx = x + 6.5
    # Two characters stacked, because the real marker is a sleeve wrapped
    # round a bollard and reads down it rather than across.
    return (post
            + f'<rect x="{x - 2:.1f}" y="{y_top + 16:.1f}" width="17" height="30" rx="2" '
              f'fill="#F97316"/>'
            + "".join(
                f'<text x="{cx:.1f}" y="{y_top + 28 + i * 13:.1f}" text-anchor="middle" '
                f'font-size="12" font-weight="800" fill="#0B1220">{ch}</text>'
                for i, ch in enumerate(label)))


def _fabricated(uid, fill_pct, capacity_l, top, bottom, ink, asset_tag, bay_marker,
                idle, *, x, w, y_top, barrel_h, cone_h, scale, ribs, legs_out) -> str:
    """A fabricated reactor: barrel, dark joint band, cone bottom, steel frame.

    Every fabricated vessel on this floor is this shape. What separates M-205
    from M-101 is not whether it has a cone - they both do - but its
    proportions and whether litre graduations are painted on it. So there is
    one drawing here with two sets of numbers, rather than two drawings that
    could drift apart.

    The level crosses the cone rather than starting at the joint, and the
    share of the volume the cone holds is derived from the cone actually
    drawn, so the picture and the arithmetic cannot disagree: a third of the
    cone's height, against the barrel's full height.
    """
    y_joint = y_top + barrel_h
    y_tip = y_joint + cone_h
    y_feet = y_tip + legs_out
    cx = x + w / 2
    tip_w = max(7.0, w * 0.06)

    # A cone of the same top radius holds a third of what that height of
    # barrel would, which is where this fraction comes from.
    cone_share = (cone_h / 3.0) / (barrel_h + cone_h / 3.0)

    frac = fill_pct / 100.0
    if frac <= cone_share:
        # Inside the cone the surface rises with the cube root of the volume,
        # because the cross-section is shrinking underneath it. A linear fill
        # here would show a nearly-empty vessel as a third full.
        depth = cone_h * (frac / cone_share) ** (1 / 3) if cone_share > 0 else 0.0
        surface_y = y_tip - depth
    else:
        surface_y = y_joint - barrel_h * ((frac - cone_share) / (1 - cone_share))

    cone = (f"M {x:.1f} {y_joint:.1f} L {x + w:.1f} {y_joint:.1f} "
            f"L {cx + tip_w / 2:.1f} {y_tip:.1f} L {cx - tip_w / 2:.1f} {y_tip:.1f} Z")

    rib_paths = ""
    if ribs:
        rib_paths = (
            f'<path d="M {x + w * 0.11:.1f} {y_joint + 4:.1f} L {cx - 4:.1f} {y_tip:.1f}" '
            f'stroke="#111827" stroke-width="4" opacity="0.85"/>'
            f'<path d="M {x + w * 0.89:.1f} {y_joint + 4:.1f} L {cx + 4:.1f} {y_tip:.1f}" '
            f'stroke="#111827" stroke-width="4" opacity="0.85"/>'
            f'<path d="M {cx:.1f} {y_joint + 4:.1f} L {cx:.1f} {y_tip:.1f}" '
            f'stroke="#111827" stroke-width="4" opacity="0.85"/>')

    # Graduations cover the barrel only, and start at the litres the cone
    # already holds - which is where the lowest mark sits on the real vessel.
    scale_svg = ""
    if scale:
        scale_svg = _graduations(capacity_l, x + 5, x + 25, y_top + 12, y_joint - 4,
                                 x - 5, from_litres=capacity_l * cone_share)

    label_y = ((y_top + y_joint) / 2 if idle else
               ((surface_y + y_joint) / 2 + 9 if fill_pct > 26 else surface_y - 12))

    return (
        # frame legs, behind the vessel
        f'<path d="M {x + w * 0.1:.1f} {y_joint - 6:.1f} L {x + 2:.1f} {y_feet:.1f}" '
        f'stroke="{_FRAME}" stroke-width="7" stroke-linecap="round"/>'
        f'<path d="M {x + w * 0.9:.1f} {y_joint - 6:.1f} L {x + w - 2:.1f} {y_feet:.1f}" '
        f'stroke="{_FRAME}" stroke-width="7" stroke-linecap="round"/>'
        f'<rect x="{x - 6:.1f}" y="{y_feet:.1f}" width="{w + 12:.1f}" height="7" rx="2" '
        f'fill="{_STEEL_DARK}"/>'
        # cone and barrel
        f'<path d="{cone}" fill="{_SHELL}" stroke="{_SHELL_EDGE}" stroke-width="2.4"/>'
        f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{w:.1f}" height="{barrel_h:.1f}" rx="8" '
        f'fill="{_SHELL}" stroke="{_SHELL_EDGE}" stroke-width="2.4"/>'
        # liquid, clipped to barrel and cone together
        f'<clipPath id="clipfab{uid}">'
        f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{w:.1f}" height="{barrel_h:.1f}" rx="8"/>'
        f'<path d="{cone}"/>'
        f'</clipPath>'
        f'<g clip-path="url(#clipfab{uid})">'
        f'<rect x="{x:.1f}" y="{surface_y:.1f}" width="{w:.1f}" '
        f'height="{y_tip - surface_y:.1f}" fill="url(#lvl{uid})" style="{_EASE}"/>'
        + _sheen(x, w, surface_y, y_tip - surface_y)
        + _surface(x, w, surface_y, uid)
        + f'</g>'
        # the dark band at the joint, then the ribs over the cone
        f'<rect x="{x - 3:.1f}" y="{y_joint - 7:.1f}" width="{w + 6:.1f}" height="11" '
        f'fill="#111827"/>'
        + rib_paths
        # bolted top flange
        + f'<rect x="{x - 5:.1f}" y="{y_top - 9:.1f}" width="{w + 10:.1f}" height="12" rx="3" '
          f'fill="{_SHELL}" stroke="{_SHELL_EDGE}" stroke-width="2"/>'
        + "".join(f'<circle cx="{x + 4 + i * (w - 8) / 7:.1f}" cy="{y_top - 3:.1f}" r="1.8" '
                  f'fill="{_STEEL_DARK}"/>' for i in range(8))
        # outlet at the tip
        + f'<rect x="{cx - 9:.1f}" y="{y_tip:.1f}" width="18" height="12" rx="2" '
          f'fill="{_STEEL}"/>'
        + scale_svg
        + _percent_label(cx, label_y, fill_pct,
                         _INK_LIGHT if (idle or fill_pct <= 26) else ink, idle)
        + _tag_plate(cx, y_top + 20, asset_tag, w=min(76.0, w * 0.7))
        + _bay_bollard(x + w + 16, y_top + 30, y_feet - 4, bay_marker)
    )


def _bulk_vertical(uid, *args) -> str:
    """M-205: tall and narrow, cone bottom, litre marks up the barrel."""
    return _fabricated(uid, *args, x=76, w=100, y_top=54, barrel_h=222, cone_h=54,
                       scale=True, ribs=False, legs_out=34)


def _cone_mixer(uid, *args) -> str:
    """M-101: short and wide, cone bottom, ribs, and no scale painted on it."""
    return _fabricated(uid, *args, x=46, w=148, y_top=96, barrel_h=162, cone_h=74,
                       scale=False, ribs=True, legs_out=34)


def _ibc_tote(uid, fill_pct, capacity_l, top, bottom, ink, asset_tag, bay_marker, idle) -> str:
    """The caged bottle on a pallet, with the ball valve at the front corner."""
    cage = "#2A7F8C"
    cage_dark = "#1B5A66"
    x, w = 40.0, 160.0
    y_top, y_bot = 96.0, 300.0
    body_h = y_bot - y_top
    fill_h = body_h * (fill_pct / 100.0)
    fill_y = y_bot - fill_h
    cx = x + w / 2

    # An open frame you see the bottle through, not a wall across it: three
    # slim rails, because four solid ones hid the very level the card is for.
    rails = "".join(
        f'<rect x="{x - 6:.1f}" y="{y_top + 40 + i * 58:.1f}" width="{w + 12:.1f}" height="6" '
        f'rx="2" fill="{cage}" opacity="0.8"/>' for i in range(3))

    return (
        # the bottle
        f'<rect x="{x:.1f}" y="{y_top:.1f}" width="{w:.1f}" height="{body_h:.1f}" rx="9" '
        f'fill="{_SHELL}" stroke="{_SHELL_EDGE}" stroke-width="2"/>'
        f'<clipPath id="clipibc{uid}"><rect x="{x:.1f}" y="{y_top:.1f}" width="{w:.1f}" '
        f'height="{body_h:.1f}" rx="9"/></clipPath>'
        f'<g clip-path="url(#clipibc{uid})">'
        f'<rect x="{x:.1f}" y="{fill_y:.1f}" width="{w:.1f}" height="{fill_h + 2:.1f}" '
        f'fill="url(#lvl{uid})" style="{_EASE}"/>'
        + _sheen(x, w, fill_y, fill_h)
        + _surface(x, w, fill_y, uid, flat=True)
        + f'</g>'
        # the cage around it: top collar, corner posts, horizontal rails
        + rails
        + f'<rect x="{x - 10:.1f}" y="{y_top - 20:.1f}" width="{w + 20:.1f}" height="22" rx="3" '
          f'fill="{cage}"/>'
          f'<rect x="{x - 10:.1f}" y="{y_top - 2:.1f}" width="12" height="{body_h + 4:.1f}" '
          f'fill="{cage}" opacity="0.95"/>'
          f'<rect x="{x + w - 2:.1f}" y="{y_top - 2:.1f}" width="12" height="{body_h + 4:.1f}" '
          f'fill="{cage}" opacity="0.95"/>'
        # filler cap on the collar
        + f'<circle cx="{cx:.1f}" cy="{y_top - 9:.1f}" r="7" fill="{cage_dark}"/>'
        # pallet base and feet
        + f'<rect x="{x - 12:.1f}" y="{y_bot + 2:.1f}" width="{w + 24:.1f}" height="18" rx="2" '
          f'fill="{cage_dark}"/>'
          f'<rect x="{x - 6:.1f}" y="{y_bot + 20:.1f}" width="16" height="10" fill="{cage_dark}"/>'
          f'<rect x="{cx - 8:.1f}" y="{y_bot + 20:.1f}" width="16" height="10" fill="{cage_dark}"/>'
          f'<rect x="{x + w - 10:.1f}" y="{y_bot + 20:.1f}" width="16" height="10" '
          f'fill="{cage_dark}"/>'
        # the ball valve, red handle and all
        + f'<rect x="{cx - 7:.1f}" y="{y_bot - 16:.1f}" width="14" height="16" rx="2" '
          f'fill="#1F2937"/>'
          f'<rect x="{cx + 5:.1f}" y="{y_bot - 12:.1f}" width="26" height="5" rx="2.5" '
          f'fill="#DC2626"/>'
        + _percent_label(cx,
                         (y_top + y_bot) / 2 if idle else
                         ((fill_y + y_bot) / 2 + 9 if fill_pct > 25 else fill_y - 12),
                         fill_pct, _INK_LIGHT if (idle or fill_pct <= 25) else ink, idle)
        + _tag_plate(cx, y_top + 8, asset_tag)
        + _bay_bollard(x + w + 22, y_top + 20, y_bot + 30, bay_marker)
    )


_RENDERERS = {
    "bulk_vertical": _bulk_vertical,
    "cone_mixer": _cone_mixer,
    "ibc_tote": _ibc_tote,
}


def vessel_svg(vessel_type: str, fill_pct: float, capacity_l: float,
               resin_colour: str = "", asset_tag: str = "", bay_marker: str = "",
               idle: bool = False, key: str = "") -> str:
    """One vessel, drawn as the kind of thing it is.

    fill_pct is what remains in it, 0-100. capacity_l only sets the spacing of
    the graduations. An idle vessel is drawn empty and grey - it has no resin
    on it, so it has no colour of its own to take.

    `key` has to differ between vessels on the same page. A gradient and a
    clip path are referenced by id, several of these end up in one document,
    and duplicate ids all resolve to the first one - so without it every tank
    on the wall would quietly take the first tank's resin colour, which is
    exactly the kind of wrong that looks fine until the day it matters.
    """
    kind = vessel_type if vessel_type in _RENDERERS else default_vessel_type(capacity_l)
    uid = "".join(ch for ch in str(key) if ch.isalnum()) or "0"
    pct = max(0.0, min(100.0, float(fill_pct or 0.0)))
    cap = max(0.0, float(capacity_l or 0.0))
    if idle:
        pct = 0.0

    low = (not idle) and pct < _LOW_LEVEL_PCT
    top, bottom, ink = _liquid_colours(resin_colour, low)

    body = _RENDERERS[kind](uid, pct, cap, top, bottom, ink,
                            str(asset_tag or "").strip(), str(bay_marker or "").strip(),
                            bool(idle))

    return (
        f'<svg viewBox="0 0 {VIEW_W} {VIEW_H}" width="100%" '
        f'style="display:block; max-height:320px; overflow:visible;" '
        f'role="img" aria-label="{html.escape(VESSEL_LABELS[kind])}, '
        f'{"idle" if idle else f"{pct:.0f} percent full"}">'
        f'<defs><linearGradient id="lvl{uid}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{bottom}"/>'
        f'<stop offset="100%" stop-color="{top}"/>'
        f'</linearGradient></defs>'
        f'{body}</svg>'
    )
