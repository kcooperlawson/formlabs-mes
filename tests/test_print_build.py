"""The shift-as-a-print-job drawing, checked without a browser.

This is decoration, which is exactly why it gets tests. Decoration is the
part nobody re-reads, so a mistake in it survives: a build that reads 40%
when the shift is at 4%, a caption that says COMPLETE at ninety-nine, a
percentage arriving as None the one morning nothing has been poured yet and
taking the wall display down with it. None of those look like bugs on the
page - they look like the plant.

Two of the assertions here are about things that were wrong once and are
invisible when they are wrong again:

  The build height must be a plain value with a transition on it, never an
  animation. Every page this appears on re-runs itself every ten seconds,
  and a looping animation restarts mid-cycle each time - which on a wall
  reads as a machine faulting rather than a shift progressing.

  Two of these on one page must not share an element id, or the second one
  silently inherits the first one's build height. That is the same class of
  fault the reactor vessels had, found the same way.
"""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import print_build as pb  # noqa: E402

FAILS, CHECKS = [], 0
IMG = "iVBORw0KGgo="          # not a real PNG; nothing here decodes it


def check(label, got, exp):
    global CHECKS
    CHECKS += 1
    if got != exp:
        FAILS.append(f"  x {label}\n      got:      {got!r}\n      expected: {exp!r}")


print("=" * 66)
print("THE SHIFT, DRAWN AS A PRINT")
print("=" * 66)

# --- the number, before it is drawn ------------------------------------------
# Everything downstream reads a percentage off a database figure, and the
# database has empty mornings, missing targets and division by zero in it.
check("nothing poured yet is nothing built", pb.clamp_pct(0), 0.0)
check("a missing figure does not raise", pb.clamp_pct(None), 0.0)
check("nor does text", pb.clamp_pct("n/a"), 0.0)
check("nor does a NaN out of pandas", pb.clamp_pct(float("nan")), 0.0)
check("a shift that beat its target is a finished part, not an overflowing one",
      pb.clamp_pct(180), 100.0)
check("and a negative one is an empty platform", pb.clamp_pct(-12), 0.0)
check("a real figure passes through", pb.clamp_pct(62.5), 62.5)
check("a numeric string does too, because settings are stored as text",
      pb.clamp_pct("47"), 47.0)
print("  the number OK")

# --- layers -------------------------------------------------------------------
check("an empty shift has written no layers", pb.layers_done(0), 0)
check("a finished one has written all of them", pb.layers_done(100), pb.LAYERS)
check("half way is half the layers", pb.layers_done(50), round(pb.LAYERS / 2))
check("the count never exceeds the part", pb.layers_done(140) <= pb.LAYERS, True)
check("and a zero layer count answers instead of dividing by zero",
      pb.layers_done(50, layers=0), 0)
print("  layers OK")

# --- the caption --------------------------------------------------------------
cap = pb.build_caption(0, 0, 900)
check("an empty shift is not called complete", "COMPLETE" in cap, False)
check("it names the layer being written", "LAYER 00" in cap, True)
check("and carries the litres, because managers do want the digits",
      "0 / 900 L" in cap, True)
check("large figures are grouped, not run together",
      "12,400" in pb.build_caption(50, 12400, 24800), True)

check("a finished shift says so in words rather than a percentage",
      pb.build_caption(100, 900, 900).startswith("BUILD COMPLETE"), True)
# 99.9% is a finished shift by every practical measure, and a wall display
# that refuses to say so over a rounding error looks broken, not precise.
check("and so does one a rounding error short",
      pb.build_caption(99.99, 900, 900).startswith("BUILD COMPLETE"), True)
check("but ninety-nine is not finished",
      "COMPLETE" in pb.build_caption(99.0, 891, 900), False)

# The break is chosen rather than left to the column width: at the width one
# of these gets on a wall display, an unbroken line wraps mid-figure.
check("the caption breaks where it was told to", "<br>" in cap, True)
check("a caption with no target still reads",
      pb.build_caption(40), f"LAYER {pb.layers_done(40):02d} / {pb.LAYERS}")
check("and a zero target does not print '/ 0'",
      "/ 0" in pb.build_caption(40, 0, 0), False)
print("  the caption OK")

# --- the part ------------------------------------------------------------------
empty = pb.cartridge_build(0, IMG, 0, 900)
part = pb.cartridge_build(47, IMG, 423, 900)
full = pb.cartridge_build(100, IMG, 900, 900)

check("the build line sits at the percentage poured", "inset(53.00% 0 0 0)" in part, True)
check("an empty shift reveals nothing", "inset(100.00% 0 0 0)" in empty, True)
check("a finished one reveals all of it", "inset(0.00% 0 0 0)" in full, True)

# The one that matters: a value with a transition, not an animation.
check("the height glides rather than loops", "transition:clip-path" in part, True)
check("and nothing on this is on a repeating timer",
      "animation" in part or "@keyframes" in part, False)

check("a shift in progress has a laser on the layer being written",
      "box-shadow:0 0 10px" in part, True)
check("a finished part does not, because nothing is being written",
      "box-shadow:0 0 10px" in full, False)
check("and an empty platform does not either", "box-shadow:0 0 10px" in empty, False)

check("the target shape is ghosted in behind, so 0% is not a blank space",
      "opacity:0.30" in empty, True)
check("and the ghost is dropped once the part is finished",
      "opacity:0.30" in full, False)

check("the built portion carries layer lines", "repeating-linear-gradient" in part, True)
check("the safari prefix is there too, because the wall PC's browser is not ours",
      "-webkit-clip-path" in part, True)

# Duplicate ids: every element resolves to the first one in the document.
a = pb.cartridge_build(20, IMG, uid="shift1")
b = pb.cartridge_build(80, IMG, uid="shift2")
check("two builds on one page do not share an id",
      a[a.index('id="'):a.index('id="') + 14] != b[b.index('id="'):b.index('id="') + 14],
      True)
check("and a caller who supplies nothing usable still gets an id",
      'id="pbb"' in pb.cartridge_build(20, IMG, uid="!!!"), True)
check("a nonsense percentage still draws a part rather than raising",
      "inset(100.00% 0 0 0)" in pb.cartridge_build(None, IMG), True)
print("  the part OK")

# --- the bars -------------------------------------------------------------------
bar = pb.layer_bar(62)
check("the bar fills to the figure given", "width:62.00%" in bar, True)
check("an empty one is empty", "width:0.00%" in pb.layer_bar(0), True)
check("a full one is full", "width:100.00%" in pb.layer_bar(100), True)
check("over target does not run off the end", "width:100.00%" in pb.layer_bar(115), True)
check("a missing figure is an empty bar, not a crash",
      "width:0.00%" in pb.layer_bar(None), True)
check("it is laid down in slices", "repeating-linear-gradient" in bar, True)
check("the colour is the caller's, so each bar keeps the meaning it had",
      "#10B981" in pb.layer_bar(50, colour="#10B981"), True)
check("and this one glides too", "transition:width" in bar, True)
check("a zero slice count cannot divide by zero",
      "repeating-linear-gradient" in pb.layer_bar(50, layers=0), True)
print("  the bars OK")

# --- the sign-in sweep ------------------------------------------------------------
sweep = pb.laser_sweep(IMG, uid="signin")
check("the sweep plays once and stops", "1 forwards" in sweep, True)
check("rather than looping forever", "infinite" in sweep, False)
check("two sweeps on one page do not share a keyframe name",
      "sweepsignin" in sweep and "sweepsignin" not in pb.laser_sweep(IMG, uid="tv"), True)
check("the glow behind the machine is neutral, not orange over orange",
      "drop-shadow(0 14px 26px rgba(0,0,0" in sweep, True)
print("  the sweep OK")

# --- escaping ----------------------------------------------------------------
check("a resin name with an ampersand in it does not break the markup",
      pb.esc("A & B"), "A &amp; B")
check("nor does a missing one", pb.esc(None), "")
print("  escaping OK")

check("a shift a whisker short of target does not say it is on its last layer",
      "46 / 46" in pb.build_caption(99.7), False)
check("and the shift that IS finished says so instead of counting layers",
      pb.build_caption(100), "BUILD COMPLETE")

# --- the finish ---------------------------------------------------------------
# The moment the shift's build completes. Whether it has already been played
# is the caller's to remember - this module has nowhere to keep that. What it
# has to guarantee is that when it is asked for, it plays once and then takes
# itself away, and that when it is not asked for it is silent. Getting that
# second half wrong gives you a celebration every ten seconds, which is not a
# celebration, it is a fault light.
fin = pb.build_finale(3120, 3000, "L", uid="tvfin")
check("the banner says what it is", "BUILD COMPLETE" in fin, True)
check("and what the shift actually poured", "3,120 / 3,000 L" in fin, True)
check("it plays once", "1 forwards" in fin, True)
check("rather than looping", "infinite" in fin, False)
# The first version faded itself out over seven seconds and reached zero
# opacity without ever having been painted: the timer starts when the browser
# inserts the element, not when the frame carrying it reaches the screen. On a
# display nobody is standing in front of, that is the same as never playing.
# What takes the band away now is the next refresh not sending it.
check("the animation only brings it in, and never takes it out again",
      "opacity:0" in fin.split("100%")[0] and "opacity:1" in fin.split("100%")[1],
      True)
check("so it cannot animate itself invisible",
      fin.split("</style>")[0].count("opacity:0;"), 1)
check("two of them on one page do not share a keyframe name",
      "fintvfin" in fin and "fintvfin" not in pb.build_finale(1, 2, uid="other"), True)

done_pass = pb.cartridge_build(100, IMG, uid="z", finale=True)
check("a finished build gets one laser pass down the part",
      "@keyframes fpassz" in done_pass, True)
check("which also plays once",
      "fpassz 2.4s ease-in-out 1 forwards" in done_pass, True)
check("an unfinished build never gets the finale pass, however it is asked",
      "fpass" in pb.cartridge_build(80, IMG, uid="z", finale=True), False)
check("and a finished build without the flag is silent, which is every refresh "
      "after the first",
      "fpass" in pb.cartridge_build(100, IMG, uid="z"), False)
print("  the finish OK")

# --- the odometer -------------------------------------------------------------
# Same rule as the build height: a plain value with a transition on it, so it
# rolls when the figure changes and sits perfectly still when it does not.
od = pb.odometer(1234, uid="tvvol")
check("every digit is a strip to roll through", od.count("transform:translateY("), 4)
check("and each lands on its own number",
      [t.split("em")[0] for t in od.split("translateY(-")[1:]], ["1", "2", "3", "4"])
check("the thousands separator is kept", ">,<" in od, True)
check("and does not roll, because it never changes",
      od.split(">,<")[0].count("transform:translateY("), 1)
check("it moves by transition", "transition:transform 900ms" in od, True)
check("and never by animation", "animation" in od, False)
check("a decimal figure keeps its point", ">.<" in pb.odometer(12.5, decimals=1), True)
check("nothing arriving does not take the card down", "0" in pb.odometer(None), True)
check("nor does text where a number was expected", "0" in pb.odometer("n/a"), True)
check("two odometers on one page do not share an element id",
      "odtvvol0" in od and "odtvvol0" not in pb.odometer(1234, uid="tvpack"), True)
print("  the odometer OK")

print("\n" + "=" * 66)
if FAILS:
    print(f"{len(FAILS)} of {CHECKS} PRINT-BUILD CHECKS FAILED:\n" + "\n".join(FAILS))
else:
    print(f"ALL {CHECKS} PRINT-BUILD ASSERTIONS PASSED")
raise SystemExit(1 if FAILS else 0)
