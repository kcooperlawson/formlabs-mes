"""the expected rate belongs to the pump, not to the plant

There was one number for the whole floor. Four hundred litres an hour, typed
into plant settings, multiplied by however long the shift had been running,
and every pace figure in the application measured against it. It cannot be
right two days running. A day with one pourer read sixty per cent behind and a
day with three read comfortably ahead, and the only thing management could do
about either was go and retype the number, which then had to be retyped
tomorrow.

The part of it that never changes day to day is the equipment. An old pump is
slower than a new one this week, next week and next year. So the rate goes on
the pump, set once when it is installed or rebuilt, and what the plant is
expected to do is worked out from the pumps that were actually certified for
the shift rather than typed by anybody.

Every existing pump takes the plant's current global figure, so nothing moves
on the day this ships. The global stays as the fallback for a pump nobody has
set yet, which is all of them until somebody starts.

Revision ID: 0020_pump_rate_targets
Revises: 0019_user_abilities
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0020_pump_rate_targets"
down_revision = "0019_user_abilities"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pump_stations",
                  sa.Column("target_lph", sa.Float(), nullable=True))
    # Seeded from what the plant is set to today rather than from a constant in
    # here, so a floor already running at 340 does not get quietly moved to 400
    # by an upgrade. NULL stays NULL where there are no settings yet: the
    # readers fall back to the global on their own, and a real number written
    # here would be a guess dressed up as a decision somebody made.
    op.execute("""
        UPDATE pump_stations
           SET target_lph = (SELECT target_lph FROM plant_settings
                              ORDER BY id LIMIT 1)
         WHERE target_lph IS NULL
    """)


def downgrade():
    op.drop_column("pump_stations", "target_lph")
