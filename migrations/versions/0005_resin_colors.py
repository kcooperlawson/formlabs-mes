"""give every resin spec a real colour

`resin_specs.color_tag` has existed since the baseline schema, but nothing
ever wrote a per-resin value to it: the column defaulted to the Formlabs Forge
accent, so every row in the table held the identical orange. A colour column
where every row is the same colour is not a colour column.

This migration fills it in, once, from `resin_palette.resin_color()` - the
plant's own colour-coded resin sheet for names it recognises, the family rule
for a revision it hasn't seen (Black V6 gets the Black colour), and a stable
hashed swatch for anything else. After this runs, what is in the column is
what the app shows, and a manager editing a colour in Resin Canvas is editing
a real stored value rather than overriding a default.

Only touches rows that were never given a colour - NULL, empty, or still
holding the old shared default. Anything a human has already set is left
exactly as it is.

No schema change at all: this is a data migration, so `downgrade()` cannot
meaningfully un-guess the colours and deliberately does nothing rather than
wiping a column a manager may since have curated by hand.

Revision ID: 0005_resin_colors
Revises: 0004_checklist_station
Create Date: 2026-09-01
"""
import os
import sys

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

# The value every row carried before colours meant anything - see the module
# docstring in resin_palette.py.
_UNSET = ("", "#EA580C", "#ea580c")


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, resin_name, color_tag FROM resin_specs")
    ).fetchall()

    for spec_id, resin_name, color_tag in rows:
        current = (color_tag or "").strip()
        if current and current not in _UNSET:
            continue  # somebody chose this on purpose; leave it alone
        conn.execute(
            sa.text("UPDATE resin_specs SET color_tag = :c WHERE id = :i"),
            {"c": resin_color(resin_name), "i": spec_id},
        )


def downgrade() -> None:
    # Intentionally a no-op. The colours this wrote are indistinguishable from
    # ones a manager has since edited, so there is nothing safe to undo.
    pass
