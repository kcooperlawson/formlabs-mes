"""A shift, drawn as a print job.

A print accretes layer by layer and so does a shift. That is not a stretched
metaphor in this building - it is the same shape of thing twice, and everybody
here already knows at a glance what a half-finished print looks like. So the
wall display builds a resin cartridge as the shift pours: the part is revealed
from the platform up, a laser sits on the layer being written, and the
cartridge is finished when the shift reaches its expected output.

The point is that it needs no legend. From the far side of the floor you can
see how the shift is going without reading a digit, which is more than can be
said for a number and a percent sign.

Three things this deliberately does NOT do:

  It does not loop. The wall display re-runs itself every ten seconds, so any
  animation on a repeating timer visibly restarts mid-cycle and reads as a
  fault. The build height is a plain CSS value recomputed each run, with a
  transition on it - so it glides when the number actually changes and sits
  perfectly still when it does not. Movement means something happened.

  It does not invent a laser sweep across the part. A travelling dot would
  have to loop, see above. The laser is a line on the current layer with a
  glow, which is what you would see looking at a machine mid-build anyway.

  It does not draw a printer. The product photographs in assets/ are the
  company's own; this positions and reveals them rather than imitating them.

Pure functions from numbers to a string of HTML - no Streamlit, no database,
no filesystem. The image is passed in already encoded, because reading and
encoding a file is the caller's business and mixing the two would make this
untestable for the sake of one line.
"""
from __future__ import annotations

import html

# Formlabs orange, which is already the accent through the rest of the app.
LASER = "#F97316"
LASER_GLOW = "rgba(249, 115, 22, 0.65)"
RESIN = "#1E3A5F"

# One rhythm for everything that moves here, matching the tokens the theme
# engine sets. SLOW is a value actually changing - a build height, a bar, a
# digit. ENTER is something arriving. SWEEP is a laser crossing the part. Three
# numbers and one curve, rather than the 0.5s / 0.75s / 1s / 1.2s / 2.6s these
# had grown into, which is what makes motion read as several people's defaults
# sitting next to each other.
EASE = "cubic-bezier(0.22, 0.61, 0.36, 1)"
SLOW = "900ms"
ENTER = "500ms"
SWEEP = "2.4s"
# The sign-in screen re-runs once as soon as the cookie component answers.
# The stroke waits out that settling render so only one of the two is ever
# seen moving. utils.COOKIE_SETTLE_SECONDS is 1.2, so this clears it.
SWEEP_DELAY = "1.4s"

# How many layer lines a full part is drawn with. High enough to read as
# layers from across a room, low enough that they do not merge into a grey
# wash at the size a wall display actually shows this at.
LAYERS = 46


def clamp_pct(value) -> float:
    """0 to 100, whatever arrives - including None, text and nonsense."""
    try:
        pct = float(value)
    except (TypeError, ValueError):
        return 0.0
    if pct != pct:            # NaN
        return 0.0
    return max(0.0, min(100.0, pct))


def layers_done(pct, layers: int = LAYERS) -> int:
    """How many layers are written at this point in the shift."""
    return int(round(clamp_pct(pct) / 100.0 * max(1, int(layers))))


def build_caption(pct, done_units=None, target_units=None, unit="L") -> str:
    """The status line under the part, as a print job would word it.

    Two lines rather than one: at the width a single vessel gets on a wall
    display, one long line wraps wherever it happens to run out of room and
    the break lands mid-figure. Deciding where it breaks is the difference
    between a status line and a mess.
    """
    pct = clamp_pct(pct)
    if pct >= 99.95:
        lead = "BUILD COMPLETE"
    else:
        # A shift at 99.7% rounds to the last layer and the caption then reads
        # "LAYER 46 / 46", which says finished on a card whose whole job is
        # saying whether it is. The last layer belongs to the finished build.
        lead = f"LAYER {min(layers_done(pct), LAYERS - 1):02d} / {LAYERS}"
    if done_units is not None and target_units:
        return (f"{lead}<br><span style=\"opacity:0.72;\">"
                f"{done_units:,.0f} / {target_units:,.0f} {unit}</span>")
    return lead


def odometer(value, decimals: int = 0, uid: str = "n") -> str:
    """A number whose digits roll to their new value instead of snapping.

    Each digit is a strip of 0 to 9 in a one-character window, moved by a
    transform with a transition on it. So this obeys the same rule as the
    build height: it is a plain value recomputed each run, not an animation on
    a timer. The wall display re-runs every ten seconds, and a number that
    re-rolled every ten seconds whether or not anything had changed would be
    movement that means nothing.

    Digits roll. Commas and the decimal point do not, because they never
    change, and a separator sliding about while the digits move is the thing
    that makes a rolling counter look cheap.

    No counters and no scripts. A CSS counter cannot carry a thousands
    separator, and a browser that did not support it would leave the figure
    blank - on the one screen in the building nobody is standing in front of.
    Worst case here is a digit that changes without sliding.
    """
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    if number != number:          # NaN
        number = 0.0
    decimals = max(0, int(decimals))
    text = f"{number:,.{decimals}f}"
    key = "".join(c for c in str(uid) if c.isalnum()) or "n"

    strip = "".join(f'<span style="display:block; height:1em;">{d}</span>'
                    for d in range(10))
    out = []
    for i, ch in enumerate(text):
        if ch.isdigit():
            out.append(
                f'<span style="display:inline-block; width:0.62em; height:1em; '
                f'overflow:hidden; vertical-align:bottom;">'
                f'<span id="od{key}{i}" style="display:block; '
                f'transform:translateY(-{int(ch)}em); '
                f'transition:transform {SLOW} {EASE} '
                f'{i * 0.04:.2f}s;">{strip}</span></span>')
        else:
            out.append(f'<span style="display:inline-block; '
                       f'vertical-align:bottom;">{esc(ch)}</span>')
    return (f'<span style="display:inline-flex; align-items:flex-end; '
            f'line-height:1; font-variant-numeric:tabular-nums;">'
            + "".join(out) + '</span>')


def build_finale(done_units=None, target_units=None, unit: str = "L",
                 uid: str = "f") -> str:
    """The moment the shift's build finishes, played once.

    Shown on the run where the target is first reached and not again, which
    is the caller's job to remember - this module has nowhere to keep that.
    That is also what takes it away again: the next refresh simply does not
    send it, so it is up for one full cycle of the wall display and then
    gone. A banner that stays up all afternoon stops meaning "just now" by
    two o'clock.

    It does NOT fade itself out on a timer, which is what the first version
    did. A timed fade starts when the browser inserts the element, and the
    element can be inserted before the frame carrying it is painted - so the
    band was reaching zero opacity without ever having been on screen. On a
    display nobody is standing in front of, an effect that might have played
    is the same as one that did not. The only animation left here is the
    half-second it takes to arrive, which cannot hide anything.
    """
    key = "".join(c for c in str(uid) if c.isalnum()) or "f"
    line = ""
    if done_units is not None and target_units:
        line = (f'<span style="font-size:1.15rem; letter-spacing:0.10em; '
                f'opacity:0.85; white-space:nowrap;">'
                f'{done_units:,.0f} / {target_units:,.0f} {esc(unit)} POURED</span>')
    return (
        f'<style>@keyframes fin{key}{{'
        f'0%{{opacity:0; transform:scale(0.985);}}'
        f'100%{{opacity:1; transform:scale(1);}}}}</style>'
        f'<div style="display:flex; align-items:center; justify-content:center; '
        f'gap:26px; flex-wrap:wrap; text-align:center; font-family:monospace; '
        f'color:#10B981; border:2px solid #10B981; border-radius:10px; '
        f'padding:14px 20px; margin:6px 0 14px 0; '
        f'background:rgba(16,185,129,0.12); '
        f'animation:fin{key} {ENTER} ease-out 1 forwards;">'
        f'<span style="font-size:2.1rem; font-weight:800; letter-spacing:0.22em; '
        f'white-space:nowrap;">BUILD COMPLETE</span>{line}</div>')


def cartridge_build(pct, image_b64: str, done_units=None, target_units=None,
                    unit: str = "L", height_px: int = 300, uid: str = "b",
                    finale: bool = False) -> str:
    """The cartridge, built to `pct` of the shift's expected output.

    The part is drawn twice: a faint ghost of the whole thing, so the target
    shape is visible from the first layer rather than appearing out of
    nothing, and the real one clipped to the height built so far. A finished
    build drops the laser and the ghost entirely, because a finished print has
    no layer being written.
    """
    pct = clamp_pct(pct)
    done = pct >= 99.95
    key = "".join(c for c in str(uid) if c.isalnum()) or "b"

    # Reveal from the bottom: the clip hides everything above the build line.
    clip = f"inset({100.0 - pct:.2f}% 0 0 0)"

    laser = ""
    if not done and pct > 0.4:
        laser = (
            f'<div style="position:absolute; left:-6%; right:-6%; '
            f'bottom:calc({pct:.2f}% - 1px); height:2px; background:{LASER}; '
            f'box-shadow:0 0 10px 2px {LASER_GLOW}; '
            f'transition:bottom {SLOW} {EASE}; z-index:4;"></div>')

    # A finished print gets taken off the plate, so the finished part lifts.
    # Only on the run that completes the build, and only far enough to read as
    # a lift rather than a layout shift - the caption underneath must not move.
    lift = ""
    if done and finale:
        lift = (f'<style>@keyframes lift{key}{{'
                f'0%{{transform:translateY(0); filter:drop-shadow(0 2px 3px '
                f'rgba(0,0,0,0.35));}}'
                f'100%{{transform:translateY(-10px); filter:drop-shadow(0 16px 22px '
                f'rgba(0,0,0,0.55));}}}}</style>')

    # One pass of the laser down the finished part, on the run where the
    # build completes and no other. Once, forwards, then gone - the same rule
    # as the sign-in sweep, for the same reason.
    if done and finale:
        laser = (
            f'<style>@keyframes fpass{key}{{'
            f'0%{{bottom:100%; opacity:0;}} 10%{{opacity:1;}}'
            f'82%{{opacity:1;}} 100%{{bottom:-2%; opacity:0;}}}}</style>'
            f'<div style="position:absolute; left:-6%; right:-6%; height:2px; '
            f'background:{LASER}; box-shadow:0 0 12px 3px {LASER_GLOW}; '
            f'animation:fpass{key} {SWEEP} ease-in-out 1 forwards; z-index:4;"></div>')

    ghost = ""
    if not done:
        ghost = (f'<img src="data:image/png;base64,{image_b64}" '
                 f'style="position:absolute; inset:0; width:100%; height:100%; '
                 f'object-fit:contain; opacity:0.30; '
                 f'filter:grayscale(1) brightness(2.9) contrast(0.45); z-index:1;"/>')

    # The layer lines ride on the built portion only, clipped with it, so they
    # appear as the part appears instead of hanging in the air above it.
    layer_lines = (
        f'<div style="position:absolute; inset:0; z-index:3; '
        f'clip-path:{clip}; -webkit-clip-path:{clip}; '
        f'transition:clip-path {SLOW} {EASE}; '
        f'background:repeating-linear-gradient(to top, '
        f'rgba(0,0,0,0.22) 0px, rgba(0,0,0,0.22) 1px, '
        f'transparent 1px, transparent {max(3, height_px // LAYERS)}px); '
        f'mix-blend-mode:multiply; pointer-events:none;"></div>')

    return (
        f'<div style="position:relative; width:100%; height:{height_px}px; '
        f'display:flex; align-items:flex-end; justify-content:center;">'
        + lift +
        f'<div id="pb{key}" style="position:relative; height:100%; aspect-ratio:0.42; '
        f'max-width:100%;'
        + (f' animation:lift{key} 1.1s {EASE} 1.4s 1 forwards;' if (done and finale) else '')
        + f'">'
        f'{ghost}'
        f'<img src="data:image/png;base64,{image_b64}" '
        f'style="position:absolute; inset:0; width:100%; height:100%; '
        f'object-fit:contain; z-index:2; clip-path:{clip}; '
        f'-webkit-clip-path:{clip}; transition:clip-path {SLOW} {EASE};"/>'
        f'{layer_lines}{laser}'
        f'</div></div>'
        f'<div style="text-align:center; margin-top:10px; font-family:monospace; '
        f'letter-spacing:0.10em; font-size:0.74rem; line-height:1.5; '
        f'white-space:nowrap; color:{"#10B981" if done else LASER};">'
        f'{build_caption(pct, done_units, target_units, unit)}</div>'
    )


def layer_bar(pct, height_px: int = 14, colour: str = "#00D2FF",
              layers: int = 34) -> str:
    """A progress bar laid down in layers rather than poured as one block.

    Same information as the bar it replaces, read the same way, but built out
    of discrete slices - because in this building that is what progress looks
    like. Costs nothing and makes the application look like it belongs to the
    company running it.
    """
    pct = clamp_pct(pct)
    slice_px = max(2, int(round(240 / max(1, int(layers)))))
    return (
        f'<div style="width:100%; height:{height_px}px; border-radius:3px; '
        f'background:#0B1220; border:1px solid #1E2B45; overflow:hidden; '
        f'position:relative;">'
        f'<div style="width:{pct:.2f}%; height:100%; '
        f'background:repeating-linear-gradient(to right, '
        f'{colour} 0px, {colour} {slice_px - 1}px, '
        f'rgba(0,0,0,0.45) {slice_px - 1}px, rgba(0,0,0,0.45) {slice_px}px); '
        f'transition:width {SLOW} {EASE};"></div>'
        f'</div>')


def laser_sweep(image_b64: str, height_px: int = 210, uid: str = "s",
                play: bool = True) -> str:
    """The printer, with a laser passing over it once as the screen arrives.

    Reported as a double glitch, and it was. The sign-in screen renders, the
    cookie component comes back a moment later with what it found, and that
    returning value re-runs the script. So the sweep started, got about a
    third of the way down, and was replaced by a fresh one starting from the
    top. Two half-strokes instead of one, which reads as a fault rather than
    an effect.

    Two things fix it and both are needed. The stroke waits before it starts,
    long enough that the first render's laser is still sitting in its delay
    when the second render replaces it - so only one of them is ever seen
    moving. And the caller stops asking for it after the screen has settled,
    with `play=False`, so typing a PIN or ticking a box does not set it off
    again. A login screen that keeps moving is one people learn to look away
    from.

    With `play=False` the machine is still drawn, and drawn identically. Only
    the laser is missing, so nothing on the screen shifts when it stops.
    """
    key = "".join(c for c in str(uid) if c.isalnum()) or "s"
    laser = ""
    if play:
        laser = (
            f'<style>@keyframes sweep{key}{{'
            f'0%{{top:-6%; opacity:0;}} 10%{{opacity:1;}}'
            f'90%{{opacity:1;}} 100%{{top:104%; opacity:0;}}}}</style>'
            f'<div style="position:absolute; left:8%; right:8%; height:2px; '
            f'top:-6%; opacity:0; background:{LASER}; '
            f'box-shadow:0 0 14px 3px {LASER_GLOW}; '
            f'animation:sweep{key} {SWEEP} ease-in-out {SWEEP_DELAY} 1 forwards;">'
            f'</div>')
    return (
        f'<div style="position:relative; height:{height_px}px; '
        f'display:flex; align-items:center; justify-content:center; '
        f'overflow:hidden;">'
        # A neutral shadow, not an orange one: the machine's own tank is
        # already orange, and a glow the same colour makes it look alight.
        f'<img src="data:image/png;base64,{image_b64}" '
        f'style="height:100%; object-fit:contain; '
        f'filter:drop-shadow(0 14px 26px rgba(0,0,0,0.65));"/>'
        f'{laser}'
        f'</div>')


def screen_sweep(uid: str = "scr", seconds: str = "1.8s") -> str:
    """One laser pass down the whole screen, as it arrives.

    The same move as the sign-in machine, at the scale of a wall. It is here
    because a screen that prints itself in is the right first impression for a
    printing company's floor display - and because it is over in under two
    seconds and then the board is just a board.

    Fixed to the viewport rather than to the page, so it crosses everything
    regardless of how far the content scrolls, and it ignores the mouse
    entirely so it cannot swallow a click on its way past.

    The caller decides when: once, on arrival. The wall display re-runs itself
    every ten seconds, and a laser crossing the room every ten seconds all
    shift is not an effect, it is a fault nobody can switch off.
    """
    key = "".join(c for c in str(uid) if c.isalnum()) or "scr"
    return (
        f'<style>@keyframes scan{key}{{'
        f'0%{{top:-4vh; opacity:0;}} 8%{{opacity:0.95;}}'
        f'92%{{opacity:0.95;}} 100%{{top:104vh; opacity:0;}}}}'
        f'.scan{key}{{position:fixed; left:0; right:0; height:2px; top:-4vh; '
        f'opacity:0; z-index:998; pointer-events:none; background:{LASER}; '
        f'box-shadow:0 0 22px 5px {LASER_GLOW}; '
        f'animation:scan{key} {seconds} ease-in-out {SWEEP_DELAY} 1 forwards;}}'
        f'</style><div class="scan{key}"></div>')


def esc(text) -> str:
    return html.escape(str(text or ""))
