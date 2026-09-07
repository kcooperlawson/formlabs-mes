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
    lead = "BUILD COMPLETE" if pct >= 99.95 else f"LAYER {layers_done(pct):02d} / {LAYERS}"
    if done_units is not None and target_units:
        return (f"{lead}<br><span style=\"opacity:0.72;\">"
                f"{done_units:,.0f} / {target_units:,.0f} {unit}</span>")
    return lead


def cartridge_build(pct, image_b64: str, done_units=None, target_units=None,
                    unit: str = "L", height_px: int = 300, uid: str = "b") -> str:
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
            f'transition:bottom 1.2s ease-in-out; z-index:4;"></div>')

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
        f'transition:clip-path 1.2s ease-in-out; '
        f'background:repeating-linear-gradient(to top, '
        f'rgba(0,0,0,0.22) 0px, rgba(0,0,0,0.22) 1px, '
        f'transparent 1px, transparent {max(3, height_px // LAYERS)}px); '
        f'mix-blend-mode:multiply; pointer-events:none;"></div>')

    return (
        f'<div style="position:relative; width:100%; height:{height_px}px; '
        f'display:flex; align-items:flex-end; justify-content:center;">'
        f'<div id="pb{key}" style="position:relative; height:100%; aspect-ratio:0.42; '
        f'max-width:100%;">'
        f'{ghost}'
        f'<img src="data:image/png;base64,{image_b64}" '
        f'style="position:absolute; inset:0; width:100%; height:100%; '
        f'object-fit:contain; z-index:2; clip-path:{clip}; '
        f'-webkit-clip-path:{clip}; transition:clip-path 1.2s ease-in-out;"/>'
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
        f'transition:width 1s ease-in-out;"></div>'
        f'</div>')


def laser_sweep(image_b64: str, height_px: int = 210, uid: str = "s") -> str:
    """The printer, with a laser passing over it once on load.

    Plays once rather than looping. The sign-in screen re-runs on its own
    timer, so "once each time the page runs" turns into a sweep every few
    seconds without any of it being on a repeating timer that could restart
    halfway through and look broken.
    """
    key = "".join(c for c in str(uid) if c.isalnum()) or "s"
    return (
        f'<style>@keyframes sweep{key}{{'
        f'0%{{top:-6%; opacity:0;}} 12%{{opacity:1;}}'
        f'88%{{opacity:1;}} 100%{{top:104%; opacity:0;}}}}</style>'
        f'<div style="position:relative; height:{height_px}px; '
        f'display:flex; align-items:center; justify-content:center; '
        f'overflow:hidden;">'
        # A neutral shadow, not an orange one: the machine's own tank is
        # already orange, and a glow the same colour makes it look alight.
        f'<img src="data:image/png;base64,{image_b64}" '
        f'style="height:100%; object-fit:contain; '
        f'filter:drop-shadow(0 14px 26px rgba(0,0,0,0.65));"/>'
        f'<div style="position:absolute; left:8%; right:8%; height:2px; '
        f'background:{LASER}; box-shadow:0 0 14px 3px {LASER_GLOW}; '
        f'animation:sweep{key} 2.6s ease-in-out 1 forwards;"></div>'
        f'</div>')


def esc(text) -> str:
    return html.escape(str(text or ""))
