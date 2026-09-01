"""give every resin spec a colour that identifies THAT resin

`resin_specs.color_tag` has existed since the baseline schema, but it was
never a per-resin colour. In practice it holds one of two things:

  * the Forge accent, on any row created through code that defaulted it -
    identical on every row, so it identifies nothing; or
  * a colour standing for the CONTAINER FORMAT rather than the material -
    one green shared by every RPS row, one blue by every V1, one rose by
    every Pigment, and so on.

Both are the same problem: a colour worn by forty different resins does not
tell an operator which resin they are holding, which is the entire job the
colour is being asked to do now that resin names render in it.

So this fills the column in from `resin_palette.resin_color()` - the plant's
own colour-coded resin sheet for names it recognises, the family rule for a
revision the sheet predates (Black V6 gets the Black colour), and a stable
hashed swatch for anything else.

WHAT IT LEAVES ALONE
--------------------
Any colour worn by fewer than SHARED_THRESHOLD distinct resin names is
treated as a deliberate per-resin choice and kept exactly as it is. That is
the test that separates "somebody picked this for this material" from "this
is the group's colour": an identity is not shared.

The threshold is a judgement call, so it is worth stating what it costs when
it is wrong. Too low and a genuine choice made for three related materials
gets overwritten - recoverable, since the picker in Resin Canvas puts it back
in one click. Too high and a group colour survives, several resins keep
rendering identically, and that is both the exact failure this migration
exists to fix and invisible until somebody notices two cartridges look the
same on screen. Three errs toward the recoverable side.

In practice the two outcomes converge on most rows anyway: a colour shared by
three Tough variants IS the Tough colour, and the palette independently
resolves all three to that same value.

No schema change - this is a data migration. `downgrade()` deliberately does
nothing: the colours it writes are indistinguishable from ones a manager has
since curated by hand, so there is nothing safe to put back.

Revision ID: 0005_resin_colors
Revises: 0004_checklist_station
Create Date: 2026-09-01
"""
import os
import sys
from collections import defaultdict

import sqlalchemy as sa
from alembic import op

# migrations/env.py already puts the project root on sys.path, but this
# migration is also exercised directly by the test suite, which applies the
# revisions without going through env.py.
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from resin_palette import resin_color  # noqa: E402

# revision identifiers, used by Alembic.
revision = "0005_resin_colors"
down_revision = "0004_checklist_station"
branch_labels = None
depends_on = None

# A colour worn by this many different resins is labelling a group, not a
# material. See the module docstring for why this number and what it costs.
SHARED_THRESHOLD = 3

# The value every row carried before colours meant anything.
_LEGACY_DEFAULT = "#EA580C"


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, resin_name, color_tag FROM resin_specs")
    ).fetchall()

    # How many DISTINCT resin names wear each colour. Distinct names, not
    # rows: the same material legitimately appears once per container format,
    # and three rows for one resin is not evidence of a shared colour.
    names_per_colour = defaultdict(set)
    for _id, name, colour in rows:
        key = (colour or "").strip().upper()
        if key:
            names_per_colour[key].add((name or "").strip().lower())

    for spec_id, resin_name, colour in rows:
        key = (colour or "").strip().upper()
        keep = (
            key
            and key != _LEGACY_DEFAULT
            and len(names_per_colour[key]) < SHARED_THRESHOLD
        )
        if keep:
            continue
        conn.execute(
            sa.text("UPDATE resin_specs SET color_tag = :c WHERE id = :i"),
            {"c": resin_color(resin_name), "i": spec_id},
        )


def downgrade() -> None:
    # Intentionally a no-op - see the module docstring.
    pass
