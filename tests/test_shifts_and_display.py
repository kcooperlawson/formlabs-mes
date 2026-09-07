"""Shift configuration, chip textures, theme readability, and undo.

Four separate pieces of work, one script, because each is small and they all
protect the same thing: that a change made for one plant or one screen does
not quietly break another.

Run after test_workflow.py - the undo section uses the shift it builds.
"""
import os
import sys
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _boot import boot, ROOT  # noqa: E402

boot(fresh=False)

import itertools  # noqa: E402
import shifts  # noqa: E402
import resin_palette as rp  # noqa: E402
import display_modes as dm  # noqa: E402
from theme_engine import contrast_ratio, Palette, build  # noqa: E402

CHECKS = 0


def check(cond, label):
    global CHECKS
    assert cond, f"FAILED: {label}"
    CHECKS += 1


def section(title):
    print("\n" + "=" * 66)
    print(title)
    print("=" * 66)


TWO = {"shift_count": 2, "shift_1_start": "06:00", "shift_2_start": "14:30"}
THREE = {"shift_count": 3, "shift_1_start": "06:00", "shift_2_start": "14:30",
         "shift_3_start": "23:00"}

# ------------------------------------------------------------------ shifts --
section("1. THIS PLANT RUNS TWO SHIFTS, NOT THREE")
check(shifts.shift_labels(TWO) == ["Shift 1", "Shift 2"], "two shifts configured")
check(shifts.picker_options(TWO) == ["Shift 1", "Shift 2", "Floater"],
      "a new record is only offered shifts the plant runs")
check("Shift 3" not in shifts.picker_options(TWO), "Shift 3 is not offered")
print("  pickers offer exactly the shifts the plant runs")

# The point of the count being a setting rather than a constant.
check(shifts.shift_labels(THREE) == ["Shift 1", "Shift 2", "Shift 3"],
      "a three-shift plant gets three")
check(shifts.shift_count({}) == 2, "missing setting defaults to two")
for junk in ({"shift_count": None}, {"shift_count": "x"}, {"shift_count": 0},
             {"shift_count": 99}):
    n = shifts.shift_count(junk)
    check(1 <= n <= shifts.MAX_TRACKED_SHIFTS, f"junk count {junk} clamps to {n}")
print("  the count is a setting, and junk values clamp instead of raising")

section("2. HISTORY DOES NOT GET REWRITTEN")
# Logs written when three shifts were offered are real production.
check("Shift 3" in shifts.picker_options(TWO, "Shift 3"),
      "editing a record that holds a retired shift still offers it")
check(shifts.picker_options(TWO, "Shift 3")[-1] == "Shift 3",
      "and offers it last, so it reads as the exception it is")
check(shifts.picker_options(TWO, "Shift 1") == shifts.picker_options(TWO),
      "a current shift adds nothing to the list")
check(shifts.is_retired("Shift 3", TWO) is True, "Shift 3 is retired here")
check(shifts.is_retired("Shift 2", TWO) is False, "Shift 2 is not")
check(shifts.is_retired("Floater", TWO) is False, "Floater is not a shift")
check(shifts.is_retired("Shift 3", THREE) is False, "and is not retired elsewhere")
print("  a retired shift stays selectable on records that already hold it")

section("3. THE SHIFT BOUNDARY WRAPS AROUND MIDNIGHT")
# The old resolver sorted start times and took the largest match, which
# cannot answer 01:30 - earlier than every start, so the naive result was
# whatever happened to be last in the list.
def at(h, m=30, settings=TWO):
    return shifts.current_shift(settings, datetime(2026, 9, 2, h, m))

check(at(6) == "Shift 1", "06:30 is the day shift")
check(at(10) == "Shift 1", "mid-morning is the day shift")
check(at(14, 30) == "Shift 2", "the handover moment belongs to the incoming shift")
check(at(22) == "Shift 2", "late evening is the second shift")
check(at(1) == "Shift 2", "01:30 is still the second shift, not nothing")
check(at(5) == "Shift 2", "05:30, minutes before handover, is still the second shift")
check(at(6, 0) == "Shift 1", "06:00 exactly starts the day shift")
print("  every hour of the clock resolves to a shift that exists")

# and the same wrap-around on a three-shift plant
check(shifts.current_shift(THREE, datetime(2026, 9, 2, 1, 30)) == "Shift 3",
      "on three shifts, 01:30 belongs to the night shift")
check(shifts.current_shift(THREE, datetime(2026, 9, 2, 23, 30)) == "Shift 3",
      "and so does 23:30")
print("  and on a three-shift plant too")

section("4. NIGHT DIMMING FOLLOWS THE PLANT'S OWN CLOCK")
check(shifts.is_outside_day_shift(TWO, datetime(2026, 9, 2, 10, 0)) is False,
      "mid-morning is not night")
check(shifts.is_outside_day_shift(TWO, datetime(2026, 9, 2, 20, 0)) is True,
      "evening is")
check(shifts.is_outside_day_shift(TWO, datetime(2026, 9, 2, 2, 0)) is True,
      "and so is the small hours")
check(shifts.is_outside_day_shift({"shift_count": 1}, datetime(2026, 9, 2, 23, 0)) is False,
      "a one-shift plant is never 'outside the day shift'")
# A plant that moves its start times moves the dimming with them.
LATE = {"shift_count": 2, "shift_1_start": "10:00", "shift_2_start": "18:00"}
check(shifts.is_outside_day_shift(LATE, datetime(2026, 9, 2, 9, 0)) is True,
      "before a late day shift starts, it is still last night")
check(shifts.is_outside_day_shift(LATE, datetime(2026, 9, 2, 11, 0)) is False,
      "and once it starts, it is not")
print("  derived from configured start times, not a hardcoded hour")

# --------------------------------------------------------------- textures --
section("5. COLOUR IS NEVER THE ONLY CHANNEL")
names = sorted(rp._PALETTE)
close, clashes = 0, []
for a, b in itertools.combinations(names, 2):
    d = rp.delta_e(rp._PALETTE[a], rp._PALETTE[b])
    if d >= rp.CONFUSABLE_DELTA_E:
        continue
    close += 1
    if rp.resin_family(a) == rp.resin_family(b):
        continue                      # same material family: alike on purpose
    if rp.resin_pattern(a) == rp.resin_pattern(b):
        clashes.append((round(d, 1), a, b))
check(not clashes, f"confusable resins from different families share a texture: {clashes}")
print(f"  {close} colour pairs are within ΔE {rp.CONFUSABLE_DELTA_E:g}; none from "
      f"different families wear the same texture")

# The specific pairs that prompted this.
for a, b in (("Clear V4", "Rigid 4000 V1"), ("Clear V4", "Rigid 10K V1"),
             ("Rigid 10K V1", "Rigid 4000 V1"), ("Grey Pro V1", "Tough 2000 V1"),
             ("Black V4", "Tough 1500 V1")):
    check(rp.delta_e(rp._PALETTE[rp._norm(a)], rp._PALETTE[rp._norm(b)]) < 5,
          f"{a} and {b} really are near-identical colours")
    check(rp.resin_pattern(a) != rp.resin_pattern(b),
          f"{a} and {b} are told apart by texture")
print("  the five near-identical pairs are all separated")

# Revisions of one family SHOULD look the same - that is information too.
for a, b in (("Clear V4", "Clear V4.1"), ("Black V4", "Black V5"),
             ("Grey V4", "Grey V4.1"), ("White V4", "White V5")):
    check(rp.resin_pattern(a) == rp.resin_pattern(b),
          f"{a} and {b} are one family and share a texture")
print("  revisions of the same family still match each other")

check(rp.resin_pattern("Black V4") == rp.resin_pattern("black v4"), "texture is case-stable")
check(rp.resin_pattern("Black V6") == rp.resin_pattern("Black V4"),
      "an unlisted revision inherits its family's texture")
chip = rp.resin_chip("Clear V4")
check("background-image" in chip or rp.resin_pattern("Clear V4") == "solid",
      "a chip actually carries its texture")
check("background-image" not in rp.resin_chip("Clear V4", pattern=False),
      "and the texture can be turned off")
check("<script>" not in rp.resin_chip('<script>x</script>'), "still escapes")
print("  textures are stable, inheritable and can be switched off")

# ----------------------------------------------------------------- themes --
section("6. EVERY THEME IS READABLE")
from themes import THEMES, PALETTES  # noqa: E402

check(len(THEMES) >= 34, f"all themes registered (found {len(THEMES)})")
check(len(PALETTES) >= 10, f"generated themes registered (found {len(PALETTES)})")
light = [n for n, p in PALETTES.items() if p.light]
check(len(light) >= 5, f"there are light themes now (found {len(light)}): {light}")
print(f"  {len(THEMES)} themes, {len(PALETTES)} generated, {len(light)} of them light")

AA = 4.5
for name, p in PALETTES.items():
    for role, fg, bg in (("body", p.body, p.ground), ("headings", p.ink, p.ground),
                         ("secondary", p.muted, p.ground),
                         ("button label", p.ground, p.accent)):
        r = contrast_ratio(fg, bg)
        check(r >= AA, f"{name}: {role} contrast {r:.1f}:1 is below {AA}:1")
print(f"  all {len(PALETTES)} generated themes clear WCAG AA on every text pair")

# The two hand-written themes that were found failing and fixed.
import re  # noqa: E402
for name in ("Default Dark", "Dracula"):
    css = THEMES[name]
    lab = re.search(r"\.telemetry-label\s*\{[^}]*color:\s*(#[0-9A-Fa-f]{6})", css).group(1)
    card = re.search(
        r"\.telemetry-grid-card\s*\{[^}]*background:\s*(?:linear-gradient\([^)]*?(#[0-9A-Fa-f]{6})|(#[0-9A-Fa-f]{6}))",
        css)
    bg = card.group(1) or card.group(2)
    r = contrast_ratio(lab, bg)
    check(r >= AA, f"{name}: card label is {r:.1f}:1 against its card, below {AA}:1")
print("  Default Dark and Dracula card labels are back above the floor")

# A light theme has to correct the dark assumptions in the shared base CSS.
for name, p in PALETTES.items():
    if p.light:
        check("light-mode corrections" in THEMES[name],
              f"{name} carries the base-CSS corrections a light ground needs")
print("  light themes correct the dark assumptions baked into BASE_UI_CSS")

# Navigation labels must take a colour from the theme rather than falling
# through to Streamlit's own. This is asserted on the CSS every theme carries,
# because it was measured at 1.35:1 in a browser: the shared base stylesheet
# painted the nav pill and never named a text colour, so the label kept
# Streamlit's near-black default on a dark pill - the six controls that get an
# operator anywhere, and the whole navigation on a phone.
from themes import BASE_UI_CSS
_nav_rules = [r for r in BASE_UI_CSS.split("}") if "stPageLink" in r or "PageLink-NavLink" in r]
check(any("color: inherit" in r for r in _nav_rules),
      "the base stylesheet gives navigation links a colour from the theme")
# The <a> alone is not enough - Streamlit colours its own markdown wrapper
# inside the link, so the descendants have to inherit too.
check(any("*" in r.split("{")[0] and "color: inherit" in r for r in _nav_rules),
      "and the label inside the link inherits it as well")
# And the sidebar, whose own container colour cuts the chain from .stApp.
check(any("stSidebar" in r and "color: inherit" in r
          for r in BASE_UI_CSS.split("}")),
      "the sidebar inherits the theme's text colour instead of Streamlit's")
print("  navigation labels take their colour from the active theme")

# The same root cause reached further than the navigation. Streamlit colours
# any element the themes do not, using a value picked for its own light base
# theme, so on a dark ground these measured 1.14-1.68:1 in a browser: the
# widget label above every control on every form, and the popover trigger,
# which additionally keeps Streamlit's near-white button surface and so needed
# a background as well as a colour.
_rules = BASE_UI_CSS.split("}")
check(any("stWidgetLabel" in r and "color: inherit" in r for r in _rules),
      "widget labels take their colour from the theme, not Streamlit's default")
check(any("stPopover" in r and "background-color" in r for r in _rules),
      "the popover trigger is given a surface rather than keeping the white one")
check(any("stPopover" in r and "color: inherit" in r for r in _rules),
      "and a colour to go on it")
# A light theme must correct the popover pill too, or it is a pale wash on a
# pale ground - the same trap the nav links were in.
for name, pal in PALETTES.items():
    if pal.light:
        check("stPopover" in THEMES[name],
              f"{name} corrects the popover surface for a light ground")
print("  widget labels and the popover trigger are legible on every theme")

section("7. DISPLAY MODES COMPOSE WITH EVERY THEME")
check(dm.display_css() == "", "neither mode on produces no CSS at all")
g = dm.display_css(glove=True)
check("min-height" in g and str(dm.GLOVE_TARGET_PX) in g, "glove mode sets a target size")
check(dm.GLOVE_TARGET_PX >= 44, "and clears the accessibility touch-target floor")
n = dm.display_css(night=True)
check("brightness(" in n, "night dimming applies a brightness filter")
check("img" in n, "and exempts images so a stamp photo keeps its true colour")
both = dm.display_css(glove=True, night=True)
check("min-height" in both and "brightness(" in both, "both together")
# Neither may set a colour: they must ride on top of the theme, not replace it.
for css in (g, n):
    check("background-color:" not in css,
          "a display mode must not paint its own colours over the theme")
print("  both are additive CSS that cannot override a theme's palette")

section("8. GENERATED CSS IS NEVER EMITTED INDENTED")
# Streamlit renders these through markdown, and CommonMark treats a
# four-space-indented line as a code block - so an indented <style> appended
# after other content is DISPLAYED as source instead of applied. That is not
# hypothetical: it shipped, and every light theme showed a grey box of CSS
# text across the top of the page until it was caught in a browser.
# Precisely: an indented <style> is only a problem when it FOLLOWS other
# content. At the very start of the string CommonMark's HTML-block rule wins
# over the indented-code rule, which is why the twenty-four hand-written
# themes have always opened with an indented <style> and always worked. The
# failure is a second, indented block appended after the first one closes -
# which is exactly what the light-mode corrections were.
for name, css in THEMES.items():
    after_first = css[css.index("</style>"):] if "</style>" in css else ""
    check("\n    <style>" not in after_first,
          f"{name}: an indented <style> follows other content and would render as text")
for name in PALETTES:
    check(THEMES[name].startswith("<style>"),
          f"{name}: generated stylesheet should start at column zero")
for label, css in (("glove", dm.glove_css()), ("night", dm.night_css())):
    check(css.startswith("<style>"), f"{label} mode CSS starts at column zero")
print(f"  all {len(THEMES)} themes and both display modes emit unindented CSS")


# --------------------------------------------------- days the plant runs --
# The stopped-record alarm asks the shift clock whether a shift is running.
# The clock only ever knew what TIME it was, so every day looked like a
# working day: on a plant that runs Monday to Friday, Saturday at six in the
# morning read as Shift 1 running with nothing logged, and the wall display
# raised an alarm about a weekend. Sunday did it again.
#
# That is not a cosmetic bug. An alarm that cries wolf every weekend is worse
# than no alarm, because by Monday nobody reads the red band and the one that
# means something looks exactly like the fifty that did not.
section("DAYS THE PLANT RUNS")

import shift_clock as sc  # noqa: E402
from datetime import datetime  # noqa: E402

WEEK = {"shift_1_start": "06:00", "shift_1_hours": 8.5,
        "shift_2_start": "14:30", "shift_2_hours": 8.5,
        "operating_days": sc.WEEKDAYS}


def at(y, mo, d, h, mi=0, settings=None):
    return sc.compute_shift_status(settings or WEEK,
                                   datetime(y, mo, d, h, mi, tzinfo=sc.PLANT_TZ))


check(at(2026, 9, 11, 9)["is_active"], "Friday morning is a working shift")
check(not at(2026, 9, 12, 9)["is_active"], "Saturday morning is not")
check(not at(2026, 9, 13, 9)["is_active"], "and neither is Sunday")
check(at(2026, 9, 14, 9)["is_active"], "Monday morning is back on")
check(at(2026, 9, 12, 9)["shift_name"] == "Off-Shift",
      "a non-working day reports Off-Shift rather than a shift nobody is on")
print("  a weekend is a weekend, not a plant that has stopped logging")

# The half of this that is easy to get wrong in the other direction. A shift
# that begins on Friday night is a FRIDAY shift at two on Saturday morning,
# and the alarm has to stay armed for it - otherwise switching the weekend off
# quietly disarms the back half of every Friday night, which is exactly when
# nobody is around to notice the record has stopped.
NIGHTS = dict(WEEK, shift_2_start="22:00", shift_2_hours=8.0)
check(at(2026, 9, 11, 23, 30, NIGHTS)["is_active"], "the Friday night shift is running")
check(at(2026, 9, 12, 2, 0, NIGHTS)["is_active"],
      "and is still watched at two on Saturday morning")
check(at(2026, 9, 12, 2, 0, NIGHTS)["shift_name"] == "Shift 2",
      "as Friday's shift, because that is the day it started")
check(not at(2026, 9, 12, 7, 0, NIGHTS)["is_active"],
      "but Saturday morning proper is off again")
check(not at(2026, 9, 13, 2, 0, NIGHTS)["is_active"],
      "and there is no Saturday night shift to watch")
print("  a shift is judged by the day it started, not the day it ends")

# What the idle state says. "Next shift tomorrow" on a Saturday is the same
# wrong answer in a smaller font.
sat = at(2026, 9, 12, 9)
check("Monday" in sat["next_shift_label"],
      "on Saturday the next shift is named as Monday's")
check("tomorrow" in at(2026, 9, 13, 9)["next_shift_label"],
      "and on Sunday it is tomorrow's")
check("runs_today" in sat and sat["runs_today"] is False,
      "the status says outright that today is not a working day")
print("  the idle state looks past the weekend rather than to tomorrow")

# The setting itself. It can silence an alarm, so every way of getting it
# wrong has to fail towards the alarm still working.
check(sc.parse_operating_days(sc.ALL_DAYS) == frozenset(range(7)), "all seven parse")
check(sc.parse_operating_days(sc.WEEKDAYS) == frozenset(range(5)), "a working week parses")
check(sc.parse_operating_days(None) == frozenset(range(7)),
      "a missing setting means every day, not no days")
check(sc.parse_operating_days("") == frozenset(range(7)), "and so does an empty one")
check(sc.parse_operating_days("nonsense") == frozenset(range(7)),
      "so does something unreadable")
check(sc.parse_operating_days("111") == frozenset(range(7)),
      "so does the wrong length")
check(sc.parse_operating_days("0000000") == frozenset(range(7)),
      "and every day switched off is a mistake in a form, not a plant")
check(sc.format_operating_days({0, 1, 2, 3, 4}) == sc.WEEKDAYS, "days round-trip to text")
check(sc.parse_operating_days(sc.format_operating_days({5, 6})) == frozenset({5, 6}),
      "and back again")
check(sc.describe_operating_days(sc.WEEKDAYS) == "Monday to Friday", "described in words")
check(sc.describe_operating_days(sc.ALL_DAYS) == "every day", "and so is every day")
check("Sat" in sc.describe_operating_days("1111110"), "an odd pattern names its days")
print("  every unreadable setting fails towards the alarm still working")

# The property that matters most for an existing install: the day this ships,
# nothing changes for anybody who has not set it.
NO_SETTING = {"shift_1_start": "06:00", "shift_1_hours": 8.5,
              "shift_2_start": "14:30", "shift_2_hours": 8.5}
for _d in range(11, 18):
    check(at(2026, 9, _d, 9, settings=NO_SETTING)["is_active"],
          f"with no setting, 2026-09-{_d} still runs as it always did")
print("  a plant that has not set this behaves exactly as before")


section("RESULT")
print(f"ALL {CHECKS} SHIFT / TEXTURE / THEME / DISPLAY ASSERTIONS PASSED")
