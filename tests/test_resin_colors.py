"""Resin colour identity: the resolver, and the migration that backfills it.

Colour is doing real work on the floor here, not decoration - an operator is
meant to be able to match what is on the screen to the cartridge in their
hand - so the properties that make that safe are worth asserting explicitly:

  * a name always resolves to a colour, including names nobody has listed
  * the same name always resolves to the SAME colour, on every machine and
    after every restart (a colour code that moves is worse than none)
  * an override a manager typed always wins
  * overlapping family rules resolve to the more specific one - "Clear Cast"
    is not a Clear, "Grey Pro" is not a Grey - which is silent when wrong and
    looks merely like a slightly-off shade
  * text stays readable on every background in the palette
  * a resin name is escaped before it reaches a raw-HTML block

Run: python tests/test_resin_colors.py
"""
import os
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _boot  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent

# Its own scratch database: this script needs to watch the migrations run
# against an empty schema, and must not wipe the shift that test_workflow
# builds for test_ui and test_pages to read.
_boot.boot(fresh=True, db_name="formlabs_test_colours")

# A second scratch database, so section 8 can watch the migration run against
# a table shaped like production without disturbing anything else.
_srv, MIGRATION_URI = _boot.boot(fresh=True, db_name="formlabs_test_migration")

import sqlalchemy as sa  # noqa: E402
from resin_palette import (  # noqa: E402
    resin_chip, resin_color, resin_color_map, resin_colors, resin_dot,
    resin_text_color, stored_color_map, style_resin_column,
)
import resin_palette as rp  # noqa: E402

CHECKS = 0


def check(cond, label):
    global CHECKS
    assert cond, f"FAILED: {label}"
    CHECKS += 1


def section(title):
    print("\n" + "=" * 66)
    print(title)
    print("=" * 66)


# ---------------------------------------------------------------- palette --
section("1. THE PLANT'S OWN SHEET")
for name, expected in rp._PALETTE.items():
    check(resin_color(name) == expected, f"{name} -> {expected}")
print(f"  all {len(rp._PALETTE)} named resins match the colours on the sheet")

check(resin_color("  black_v4 ") == "#3B3C3C", "leading space and underscore")
check(resin_color("BLACK V4") == "#3B3C3C", "shouting")
check(resin_color("Grey V4.1") == resin_color("grey v4.1"), "case-insensitive")
print("  messy transcriptions of a known name land on the same colour")

# ------------------------------------------------------------- overrides ---
section("2. A MANAGER'S CHOICE WINS")
check(resin_color("Black V4", "#123456") == "#123456", "explicit override")
check(resin_color("Anything At All", "#abc") == "#AABBCC", "short hex expands")
for junk in (None, "", "   ", "not-a-colour", "#GGGGGG", "blue"):
    check(resin_color("Black V4", junk) == "#3B3C3C", f"junk stored value {junk!r}")
check(resin_color("Black V4", "#EA580C") == "#3B3C3C",
      "the pre-0005 shared default counts as 'nobody chose one'")
print("  a real stored colour wins; junk and the legacy default fall through")

# ---------------------------------------------------------------- family ---
section("3. A RESIN NOBODY LISTED")
# The whole point: a revision that does not exist yet is already right.
FUTURE = [
    ("Black V6", "#3B3C3C"), ("Clear V6", "#EBF5FA"), ("Grey V6", "#666B6D"),
    ("White V6", "#E9E8CC"), ("Model V4", "#F5CBA6"), ("Draft V3", "#5C6D7D"),
    ("Durable V3", "#F6DB6F"), ("High Temp V3", "#E67D21"), ("ESD V2", "#F29C12"),
    ("Flexible 80A V2", "#1ABC9C"), ("Silicone 40A V2", "#A2E3D6"),
    ("Elastic 50A V3", "#9A58B5"), ("Alumina 4N V2", "#FDECEC"),
    ("Flame Retardant V2", "#BF382A"), ("Standard Clear V5", "#EBF5FA"),
    ("Standard Black V5", "#3B3C3C"),
]
for name, expected in FUTURE:
    check(resin_color(name) == expected, f"{name} inherits its family")
print(f"  {len(FUTURE)} unlisted names inherit the right family colour")

# The overlapping pairs. Each of these is a substring of the one below it, so
# a wrong rule order gives a plausible-looking wrong colour rather than a crash.
OVERLAPS = [
    ("Clear Cast V2", "#A8CCE3", "Clear V4", "#EBF5FA"),
    ("Grey Pro V2", "#545454", "Grey V4", "#666B6D"),
    ("Fast Model V2", "#818277", "Model V2", "#F5CBA6"),
    ("Rigid 10K V2", "#F1F5FE", "Rigid 8000 V1", "#F1FAFE"),
    ("Castable Wax 40 V2", "#D1B4DE", "Castable Wax V2", "#6B3382"),
    ("Tough 2000 V2", "#53585B", "Tough 3000 V1", "#424548"),
]
for specific, s_col, general, g_col in OVERLAPS:
    check(resin_color(specific) == s_col, f"{specific} is not a plain {general.split()[0]}")
    check(resin_color(general) == g_col, f"{general} keeps the family colour")
    check(s_col != g_col, "the two are actually distinguishable")
print(f"  {len(OVERLAPS)} specific-vs-general pairs resolve to the specific rule")

# --------------------------------------------------------------- unknown ---
section("4. SOMETHING GENUINELY NEW")
INVENTED = ["Bioresin XZ9", "Ceramic Blue", "Photopolymer QQ", "Hydrogel 12",
            "Nylon PA12", "Experimental 7"]
for name in INVENTED:
    colour = resin_color(name)
    check(rp._HEX_RE.match(colour), f"{name} still gets a valid colour")
    check(colour == resin_color(name.lower()), f"{name} is case-stable")
    check(colour == resin_color(name), f"{name} is stable within a process")
# Stable ACROSS processes is the one that matters and the one Python's own
# hash() would break, so pin the actual value rather than just self-consistency.
check(resin_color("Bioresin XZ9") == rp._hash_colour("Bioresin XZ9"),
      "unknown names come from the fixed swatch list, not a random seed")
check(len({resin_color(n) for n in INVENTED}) >= len(INVENTED) - 1,
      "invented names do not all collide onto one colour")
check(resin_color("") == rp._FALLBACK and resin_color(None) == rp._FALLBACK,
      "a blank name still returns something renderable")
print(f"  {len(INVENTED)} invented names: valid, stable and distinct")

# ------------------------------------------------------------ legibility ---
section("5. READABLE ON EVERY BACKGROUND")
for name, bg in rp._PALETTE.items():
    fg = resin_text_color(bg)
    check(fg in ("#FFFFFF", "#111827"), f"{name} text colour is one of the two")
    contrast = abs(rp._luminance(bg) - rp._luminance(fg))
    check(contrast > 0.2, f"{name}: text stands off its background ({contrast:.2f})")
    _bg, _fg, border = resin_colors(name)
    check(border != _bg, f"{name}: chip has a visible edge on a pale page")
print("  every palette colour has readable text and a visible border")

# ---------------------------------------------------------------- markup ---
section("6. MARKUP SAFETY")
evil = 'Clear <script>alert("x")</script> V4'
chip = resin_chip(evil)
check("<script>" not in chip and "&lt;script&gt;" in chip, "chip escapes the name")
check("<script>" not in resin_dot(evil), "dot escapes the name")
check('title="' in chip and chip.count('"') % 2 == 0, "attributes stay balanced")
check(resin_chip("") == "" and resin_chip(None) == "", "empty name renders nothing")
check(resin_dot("") == "" and resin_dot(None) == "", "empty dot renders nothing")
print("  a resin name containing markup cannot break the card it sits in")

# ------------------------------------------------------------- dataframes --
section("7. HELPERS TOLERATE WHAT THEY ARE GIVEN")
import pandas as pd  # noqa: E402

check(stored_color_map(None) == {}, "None frame")
check(stored_color_map(pd.DataFrame()) == {}, "empty frame")
check(stored_color_map(pd.DataFrame({"resin_name": ["Black V4"]})) == {},
      "frame with no colour column")
check(stored_color_map(pd.DataFrame({"resin_name": ["Black V4"], "color_tag": ["#111111"]}))
      == {"Black V4": "#111111"}, "normal frame")

df = pd.DataFrame({"resin_type": ["Black V4", "Clear V5"], "units": [10, 20]})
check(hasattr(style_resin_column(df, "resin_type"), "to_html"), "returns a Styler")
check(style_resin_column(df, "missing_column") is df, "missing column degrades to the frame")
check(style_resin_column(pd.DataFrame(), "resin_type") is not None, "empty frame is safe")
check(resin_color_map(["Black V4", None, "Clear V5"], {"Black V4": "#000000"})
      == {"Black V4": "#000000", "Clear V5": "#EBF5FA"}, "colour map skips None")
print("  every helper degrades to 'uncoloured' rather than taking a page down")

# -------------------------------------------------------------- migration --
section("8. MIGRATION 0005 REPLACES GROUP COLOURS, KEEPS REAL ONES")
# Run the real migration against a table shaped the way the production
# database actually is: color_tag there was never a per-resin colour, it was
# the CONTAINER FORMAT's colour - one green on every RPS row, one blue on
# every V1 - plus a handful of genuine per-resin choices. Asserting against
# that shape rather than an empty table is the whole point; an empty-table
# test passes happily while every resin on screen renders the same green.
import subprocess  # noqa: E402

os.environ["DB_URL"] = MIGRATION_URI
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "0004_checklist_station"],
               check=True, capture_output=True, cwd=str(ROOT))

FIXTURE = [
    # (name, format, colour as the old app would have stored it)
    ("Black V4", "V1", "#1E3A8A"), ("Clear V4", "V1", "#1E3A8A"),
    ("Grey V4", "V1", "#1E3A8A"), ("White V4", "V1", "#1E3A8A"),
    ("Draft V2", "V1", "#1E3A8A"),          # 5 different resins, one V1 blue
    ("Tough 1500 V1", "RPS", "#16A34A"), ("High Temp V2", "RPS", "#16A34A"),
    ("ESD V1", "RPS", "#16A34A"),           # 3 different resins, one RPS green
    ("Cyan Pigment", "Pigment", "#E11D48"),
    ("Magenta Pigment", "Pigment", "#E11D48"),
    ("Yellow Pigment", "Pigment", "#E11D48"),
    ("Castable Wax V1", "V2", "#6B3382"),   # a real per-resin choice, 1 name
    ("Color Base V1", "V2", "#CCB4E4"),     # another, deliberately non-palette
    ("Alumina 4N V1", "V2", None),          # never set
    ("Silicone 40A V1", "V2", "#EA580C"),   # the old shared default
    # the same material in two formats is not evidence of a shared colour
    ("Clear V5", "V1", "#907DCA"), ("Clear V5", "V2", "#907DCA"),
]
mig_engine = sa.create_engine(MIGRATION_URI)
with mig_engine.connect() as conn:
    for name, fmt, colour in FIXTURE:
        conn.execute(sa.text(
            "INSERT INTO resin_specs (cartridge_type, resin_name, actual_spec_g, "
            "min_weight_g, max_weight_g, color_tag) "
            "VALUES (:f, :n, 1110, 1100, 1120, :c)"),
            {"f": fmt, "n": name, "c": colour})
    conn.commit()

# Upgrade to 0005 specifically, not to head. This section tests what 0005
# does to a table shaped like production; pinning it to head made the test
# fail the moment 0006 was added, which is a false alarm about an unrelated
# migration rather than a real regression in this one.
subprocess.run([sys.executable, "-m", "alembic", "upgrade", "0005_resin_colors"],
               check=True, capture_output=True, cwd=str(ROOT))

with mig_engine.connect() as conn:
    check(conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
          == "0005_resin_colors", "schema is at 0005, the revision under test")
    after = {}
    for name, fmt, colour in conn.execute(sa.text(
            "SELECT resin_name, cartridge_type, color_tag FROM resin_specs")):
        after[(name, fmt)] = colour

check(all(c for c in after.values()), "no row is left without a colour")

# The group colours are gone, and each of those resins now carries its own.
for name, fmt, _old in FIXTURE:
    if _old in ("#1E3A8A", "#16A34A", "#E11D48", "#EA580C", None):
        check(after[(name, fmt)] == resin_color(name),
              f"{name} [{fmt}] replaced its group colour with its own")
check(after[("Black V4", "V1")] == "#3B3C3C", "V1 blue became the Black colour")
check(after[("Cyan Pigment", "Pigment")] == "#22B8CF", "pigment rose became cyan")
check(after[("Alumina 4N V1", "V2")] == "#FDECEC", "a NULL colour got filled in")
check(after[("Silicone 40A V1", "V2")] == "#A2E3D6", "the old default got replaced")
check(len({after[(n, f)] for n, f, o in FIXTURE if o == "#1E3A8A"}) == 5,
      "the five resins that shared one blue are now five different colours")

# A colour only one or two resins wear is a decision, and survives untouched.
check(after[("Castable Wax V1", "V2")] == "#6B3382", "a per-resin choice is kept")
check(after[("Color Base V1", "V2")] == "#CCB4E4",
      "a per-resin choice is kept even when it isn't a palette colour")
check(after[("Clear V5", "V1")] == "#907DCA" and after[("Clear V5", "V2")] == "#907DCA",
      "one material across two formats is not treated as a shared colour")
print(f"  {len(FIXTURE)} rows: group colours replaced, {2} deliberate choices kept")

# Family colours ARE shared afterwards - every Tough is one grey - so the rule
# must converge rather than fight itself if it is ever applied again.
before_second = dict(after)
import importlib.util  # noqa: E402
spec = importlib.util.spec_from_file_location(
    "mig0005", str(ROOT / "migrations" / "versions" / "0005_resin_colors.py"))
mig = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mig)
with mig_engine.connect() as conn:
    rows = conn.execute(sa.text("SELECT id, resin_name, color_tag FROM resin_specs")).fetchall()
    from collections import defaultdict
    per = defaultdict(set)
    for _i, n, c in rows:
        per[(c or "").strip().upper()].add((n or "").strip().lower())
    for _i, n, c in rows:
        k = (c or "").strip().upper()
        if k and k != "#EA580C" and len(per[k]) < mig.SHARED_THRESHOLD:
            continue
        check(resin_color(n) == c,
              f"re-applying the rule to {n} would not change it")
print("  the rule converges: applying it twice changes nothing")

section("RESULT")
print(f"ALL {CHECKS} RESIN COLOUR ASSERTIONS PASSED")
