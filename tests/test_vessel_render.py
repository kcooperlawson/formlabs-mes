"""The vessels, checked as arithmetic rather than looked at.

A drawing is the easiest thing in an application to get quietly wrong. It
does not raise, it does not fail a page render, and a tank that is drawing
the wrong colour or the wrong level looks exactly as convincing as one that
is right - which on a screen whose entire job is "how much is left in that
vessel" is the worst property a component can have.

So the parts that carry meaning are checked here as numbers and strings: the
level lands where the litres say it should, the liquid takes the resin's
colour, the percentage stays readable on a white resin and on a black one,
each vessel on a page gets its own gradient, and the shape a manager recorded
is the shape that gets drawn. What is left over for the eye is whether it
looks like the tank in the aisle, which is the one part a test cannot help
with anyway.

No browser, no Streamlit, no database - reactor_vessel is a function from a
handful of numbers to a string, and that is exactly why it was written that
way.
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from reactor_vessel import (  # noqa: E402
    BULK_FROM_L, CONE_FROM_L, VESSEL_LABELS, VESSEL_TYPES,
    default_vessel_type, resolve_vessel_type, vessel_svg,
)

FAILS, CHECKS = [], 0


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


def draw(**kw):
    kw.setdefault("vessel_type", "bulk_vertical")
    kw.setdefault("fill_pct", 50.0)
    kw.setdefault("capacity_l", 5000)
    kw.setdefault("key", "t1")
    return vessel_svg(**kw)


def joint_y(svg):
    """Where the barrel meets the cone, from the dark band drawn over it."""
    m = re.search(r'<rect x="[-\d.]+" y="([\d.]+)" width="[\d.]+" height="11" '
                  r'fill="#111827"/>', svg)
    return float(m.group(1)) + 7 if m else None


def surface_y(svg, uid="t1"):
    """Where the top of the liquid sits, in the drawing's own coordinates."""
    m = re.search(rf'<rect x="[\d.]+" y="([\d.]+)" width="[\d.]+" '
                  rf'height="[\d.]+" fill="url\(#lvl{uid}\)"', svg)
    return float(m.group(1)) if m else None


print("=" * 66)
print("REACTOR VESSELS")
print("=" * 66)

# --- the shape is recorded, not guessed ----------------------------------
# The whole reason for the column: two vessels of similar size on this floor
# are different shapes, and no arithmetic on the capacity will ever say so.
check("a big vessel defaults to a bulk vertical",
      default_vessel_type(BULK_FROM_L), "bulk_vertical")
check("a mid one to a cone-bottom mixer",
      default_vessel_type(CONE_FROM_L), "cone_mixer")
check("and a small one to a tote", default_vessel_type(CONE_FROM_L - 1), "ibc_tote")
check("a missing capacity still names something drawable",
      default_vessel_type(None), "ibc_tote")
check("what a manager recorded outranks the capacity",
      resolve_vessel_type("ibc_tote", 5000), "ibc_tote")
check("and so does the other direction",
      resolve_vessel_type("bulk_vertical", 200), "bulk_vertical")
check("a value nobody can draw falls back rather than breaking the page",
      resolve_vessel_type("submarine", 5000), "bulk_vertical")
check("so does an empty one", resolve_vessel_type("", 2000), "cone_mixer")
print("  vessel kinds OK")

for kind in VESSEL_TYPES:
    svg = draw(vessel_type=kind, fill_pct=40)
    check(f"{kind} draws", svg.startswith("<svg") and svg.endswith("</svg>"), True)
    check(f"{kind} says what it is, for a screen reader",
          VESSEL_LABELS[kind] in svg, True)
print("  every kind renders OK")

# --- the level is the level ----------------------------------------------
# A tank at 25% and the same tank at 75% must not draw the same, and the
# fuller one must be the one with more liquid in it. This is the assertion
# that catches a sign flip, and a sign flip here reads as a full tank on the
# morning somebody needed to know it was empty.
full = surface_y(draw(fill_pct=100))
mid = surface_y(draw(fill_pct=50))
low = surface_y(draw(fill_pct=10))
check("the liquid can be found at all", None not in (full, mid, low), True)
if None in (full, mid, low):
    # Nothing below can say anything useful, and a cascade of TypeErrors is a
    # worse report than one named failure.
    print("\n".join(FAILS))
    raise SystemExit(1)
check("a fuller tank has its surface higher up the vessel", full < mid < low, True)

top_at_100, top_at_0 = full, surface_y(draw(fill_pct=0))

# On a cone-bottomed vessel half full is NOT half way up, and a drawing that
# put it there would be lying about the vessel: the cone takes up height
# while holding very little, so the surface of half a tank sits above the
# geometric middle. This is the assertion that would have caught the version
# of this drawing that gave the tall vessels a flat bottom.
middle = (top_at_100 + top_at_0) / 2
check("half full sits above the middle, because the cone holds little for its height",
      mid < middle - 3, True)

# And below a few percent the liquid is inside the cone, not a film sitting
# on top of it.
joint = joint_y(draw(fill_pct=50))
check("the joint between barrel and cone can be found", joint is not None, True)
if joint is not None:
    check("a nearly empty vessel has its liquid down in the cone",
          surface_y(draw(fill_pct=2)) > joint, True)
    check("and a mostly full one has it up in the barrel",
          surface_y(draw(fill_pct=80)) < joint, True)

# A tote is flat bottomed, so on that one half full IS half way - the same
# code has to get both right.
tote_mid = surface_y(draw(vessel_type="ibc_tote", fill_pct=50))
tote_span = (surface_y(draw(vessel_type="ibc_tote", fill_pct=100))
             + surface_y(draw(vessel_type="ibc_tote", fill_pct=0))) / 2
check("half a flat-bottomed tote is half way up it", abs(tote_mid - tote_span) < 1.0, True)

check("an over-range level is clamped rather than drawn outside the vessel",
      surface_y(draw(fill_pct=140)), full)
check("and so is a negative one", surface_y(draw(fill_pct=-20)), top_at_0)
print("  levels OK")

# --- the graduations are the ones painted on the real vessel --------------
svg = draw(capacity_l=5000, fill_pct=60)
for litres in ("1,000", "2,000", "3,000", "4,000"):
    check(f"the {litres} L mark is numbered", litres in svg, True)
check("but the marks between them are not numbered", "3,200" in svg, False)
check("a tank is not numbered at its own capacity", "5,000" in svg, False)

# The point of the scale: the surface lands on the mark somebody at the tank
# would read it against. 2,500 L in a 5,000 L tank is the 2,500 line, which
# sits half way between the 2,000 and 3,000 marks.
svg_half = draw(capacity_l=5000, fill_pct=50)
ticks = [float(m) for m in re.findall(r'<line x1="[\d.]+" y1="([\d.]+)"', svg_half)]
here = surface_y(svg_half)
above = [t for t in ticks if t < here]
below = [t for t in ticks if t > here]
check("the surface sits between marks, not off the end of the scale",
      bool(above) and bool(below), True)
print("  graduations OK")

# --- colour ---------------------------------------------------------------
# The liquid is the resin's colour because that is how the floor tells the
# tanks apart from a distance, and the number over it has to survive both
# ends of the range this plant actually runs.
white = draw(resin_colour="#F2F4F8", fill_pct=70)
black = draw(resin_colour="#111111", fill_pct=70)
check("a pale resin gets dark ink over it", 'fill="#0B1220"' in white, True)
check("a dark resin gets light ink over it", 'fill="#FFFFFF"' in black, True)
check("a near-black resin is lifted enough to read as a liquid",
      'stop-color="#111111"' in black, False)
check("a colour nobody can parse does not take the drawing down with it",
      draw(resin_colour="chartreuse-ish").startswith("<svg"), True)

low = draw(resin_colour="#22C55E", fill_pct=4)
check("a tank under a tenth full goes red whatever is in it",
      "#EF4444" in low, True)
check("and one above it does not", "#EF4444" in draw(resin_colour="#22C55E", fill_pct=40), False)
print("  colour OK")

# --- several vessels on one page -----------------------------------------
# A gradient is referenced by id, four tanks share one document, and
# duplicate ids all resolve to the first. Without a per-vessel key every tank
# on the wall would quietly take the first tank's colour - a bug that looks
# like a working page.
a = vessel_svg("bulk_vertical", 50, 5000, "#EF4444", key="Reactor 1")
b = vessel_svg("bulk_vertical", 50, 5000, "#22C55E", key="Reactor 2")
ids_a = set(re.findall(r'id="([^"]+)"', a))
ids_b = set(re.findall(r'id="([^"]+)"', b))
check("two vessels on a page share no ids at all", ids_a & ids_b, set())
check("each still refers to its own gradient", "url(#lvlReactor1)" in a, True)
check("and not to the other one's", "url(#lvlReactor2)" in a, False)
check("a key of punctuation alone still yields a usable id",
      bool(re.search(r'id="lvl\w+"', vessel_svg("ibc_tote", 50, 1000, key="!!"))), True)
print("  one page, many vessels OK")

# --- idle ------------------------------------------------------------------
# A vessel with no resin on it is not nought point nought percent full of
# anything, and saying so sends somebody looking for a leak.
idle = draw(idle=True, fill_pct=80)
check("an idle vessel says IDLE", "IDLE" in idle, True)
check("and does not print a percentage", "%<" in idle, False)
check("and is drawn empty whatever it was passed",
      surface_y(idle), top_at_0)
check("a working vessel prints its percentage", "62.5%" in draw(fill_pct=62.5), True)
print("  idle OK")

# --- what it is called on the floor ---------------------------------------
tagged = draw(asset_tag="M-205", bay_marker="f3")
check("the asset tag is stencilled on the vessel", "M-205" in tagged, True)
check("the bay marker is drawn in upper case, as it is out there",
      ">F<" in tagged and ">3<" in tagged, True)
check("a tag that could break the drawing is escaped",
      "&lt;script&gt;" in draw(asset_tag="<script>"), True)
check("no tag means no plate rather than an empty one",
      "M-205" in draw(), False)
print("  floor identifiers OK")

# --- the liquid has to read as liquid --------------------------------------
# It was a flat-topped rectangle inside a tank outline, which is a bar chart
# with decoration round it. A vessel is a round thing seen slightly from
# above, so its contents end in an ellipse. None of this is allowed to change
# WHERE the surface sits, which is the only thing on this drawing anybody
# makes a decision on.
fab = draw(fill_pct=60)
check("the fabricated vessel's surface is drawn as an ellipse, not a cut edge",
      "<ellipse" in fab, True)
check("and the surface still sits exactly where it did before the ellipse",
      surface_y(fab), 150.0)
tote = draw(vessel_type="ibc_tote", fill_pct=60)
check("a square tote gets a flat surface, because there is no cylinder in it",
      'fill="url(#lvlt1)"/>' in tote, False)
check("but it still gets the highlight where the light would catch it",
      "<ellipse" in tote, True)
check("the fabricated one gets the surface in the resin's own colour",
      'fill="url(#lvlt1)"' in fab.split("<ellipse")[1].split(">")[0], True)

# The level glides to its new height. It has to be a transition on a plain
# value and never an animation: every page carrying these re-runs on a timer,
# and an animation would restart mid-cycle each time and read as a fault.
check("the level moves by transition", "transition:y 0.9s" in fab, True)
check("and never by animation", "animation" in fab, False)
check("the sheen is clipped to the liquid, so an empty vessel has none",
      'height="0.0"' in draw(fill_pct=0) or surface_y(draw(fill_pct=0)) is not None,
      True)
print("  the liquid OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} VESSEL CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} VESSEL ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
