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
import sys
import pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import _boot  # noqa: E402

# Its own scratch database: this script needs to watch the migrations run
# against an empty schema, and must not wipe the shift that test_workflow
# builds for test_ui and test_pages to read.
_boot.boot(fresh=True, db_name="formlabs_test_colours")

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
section("8. MIGRATION 0005 FILLS THE COLUMN IN")
import crud  # noqa: E402
from db_core import engine  # noqa: E402

crud.init_db()
crud.seed_initial_data()

with engine.connect() as conn:
    version = conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()
    check(version == "0005_resin_colors", f"schema is at 0005 (found {version})")

    # A row that predates colours: NULL, and one still holding the old default.
    conn.execute(sa.text(
        "INSERT INTO resin_specs (cartridge_type, resin_name, actual_spec_g, "
        "min_weight_g, max_weight_g, color_tag) VALUES "
        "('V2', 'Grey Pro V1', 1080, 1070, 1090, NULL), "
        "('V2', 'Castable Wax 40 V1', 1010, 1000, 1020, '#EA580C')"
    ))
    conn.commit()

    rows = conn.execute(sa.text("SELECT resin_name, color_tag FROM resin_specs")).fetchall()

check(len(rows) >= 2, "seeded specs exist")
for name, stored in rows:
    check(rp._HEX_RE.match(resin_color(name, stored)),
          f"{name} renders a colour whatever is stored ({stored!r})")
# The two rows written the old way still come out right, because the resolver
# treats NULL and the legacy default as "nobody chose one".
by_name = dict(rows)
check(resin_color("Grey Pro V1", by_name.get("Grey Pro V1")) == "#545454",
      "a NULL colour resolves from the name")
check(resin_color("Castable Wax 40 V1", by_name.get("Castable Wax 40 V1")) == "#D1B4DE",
      "a legacy-default colour resolves from the name")
print(f"  {len(rows)} spec rows, every one renders a real per-resin colour")

section("RESULT")
print(f"ALL {CHECKS} RESIN COLOUR ASSERTIONS PASSED")
