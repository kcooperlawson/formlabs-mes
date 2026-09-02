"""make the number of shifts a setting rather than an assumption

The app was written assuming three shifts and offered "Shift 3" in every
picker. This plant runs two. Hardcoding two instead of three would just move
the wrong assumption, so the count becomes a plant setting.

Defaults to 2, which is correct for this plant today and is also the safe
default for a fresh install: offering a shift nobody works produces empty
buckets in every report, while a plant that adds one changes a number in the
admin screen rather than waiting on a code change.

Nothing rewrites existing rows. Logs written when three shifts were offered
carry "Shift 3" and are real production; they keep displaying and filtering
exactly as before. See shifts.py for how the pickers keep offering a retired
shift to any record that already holds one, so editing an old record cannot
silently reassign somebody's work.

Revision ID: 0007_shift_count
Revises: 0006_check_weight
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0007_shift_count"
down_revision = "0006_check_weight"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "plant_settings",
        sa.Column("shift_count", sa.Integer(), nullable=True, server_default="2"),
    )
    # Existing installs have exactly one settings row; give it the value
    # rather than leaving it NULL, so nothing has to reason about NULL later.
    op.execute("UPDATE plant_settings SET shift_count = 2 WHERE shift_count IS NULL")


def downgrade() -> None:
    op.drop_column("plant_settings", "shift_count")
