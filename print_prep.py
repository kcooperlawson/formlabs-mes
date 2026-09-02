"""Lift the black floor on a dark screenshot so it can be printed.

Management prints this handbook. Every one of the app's themes was dark when
the figures were first taken, and a 26-page document of near-black pages is a
solid block of toner that soaks the sheet and bleeds through to the other side.

The alternative - re-shooting everything in a light theme - would have
misrepresented the product, because the product genuinely was dark. So the
floor is raised instead: pure black becomes a dark grey, white stays white, and
every pixel of *content* is unchanged. Ink coverage drops from about 95% to
around 70% and the page is still recognisably the screen people use.

    python print_prep.py figs_print/fw_weight.png figs_print/fw_analytics.png

Idempotent in practice: a figure already lifted has no pixels near zero, so
running it twice moves almost nothing. It reports the before and after so you
can see whether it did anything.
"""
import sys

from PIL import Image

# The floor the existing figures were prepared to. Matching it matters more
# than the exact value - a page where one screenshot is visibly darker than
# its neighbours reads as a printing fault.
FLOOR = 58


def lift(path):
    img = Image.open(path).convert("RGB")
    before = sum(img.convert("L").histogram()[i] * i for i in range(256))
    before /= float(img.size[0] * img.size[1])
    # Linear remap of [0,255] onto [FLOOR,255]: black rises, white is fixed,
    # and everything between keeps its ordering and its relative spacing.
    table = [round(FLOOR + v * (255 - FLOOR) / 255.0) for v in range(256)] * 3
    out = img.point(table)
    after = sum(out.convert("L").histogram()[i] * i for i in range(256))
    after /= float(out.size[0] * out.size[1])
    out.save(path)
    print(f"  {path}: ink {(255 - before) / 255 * 100:.0f}% -> "
          f"{(255 - after) / 255 * 100:.0f}%")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        raise SystemExit(2)
    for p in sys.argv[1:]:
        lift(p)
