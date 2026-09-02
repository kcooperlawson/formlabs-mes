"""record the weight a cartridge actually came out at

`resin_specs` has always held the target fill weight and the tolerance
window, and nothing has ever recorded a measurement against it - so the app
could say how many units were poured but not how much resin went into them.
A pump running high sits inside spec on every cartridge while giving away
resin on every cartridge, and there was no column that could show it.

Three columns on production_logs, all nullable, because the reading is
optional by design and most rows will not have one:

  check_weight_g      what the scale said, in grams
  weight_deviation_g  measured minus the target that applied at the time
  weight_status       in / under / over, judged at capture

`weight_status` is denormalized on purpose, the same way `verify_status`
already is. Judging it at capture time means a later edit to a resin's
tolerances cannot silently re-judge readings somebody already took, and it
keeps "show me every out-of-band log" a single indexed scan rather than a
join against a spec that may since have moved.

Purely additive - no existing column is touched and every pre-existing log
stays valid with all three left NULL.

Revision ID: 0006_check_weight
Revises: 0005_resin_colors
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0006_check_weight"
down_revision = "0005_resin_colors"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("production_logs", sa.Column("check_weight_g", sa.Float(), nullable=True))
    op.add_column("production_logs", sa.Column("weight_deviation_g", sa.Float(), nullable=True))
    op.add_column("production_logs", sa.Column("weight_status", sa.String(10), nullable=True))
    op.create_index("ix_production_logs_weight_status", "production_logs", ["weight_status"])


def downgrade() -> None:
    op.drop_index("ix_production_logs_weight_status", table_name="production_logs")
    op.drop_column("production_logs", "weight_status")
    op.drop_column("production_logs", "weight_deviation_g")
    op.drop_column("production_logs", "check_weight_g")
