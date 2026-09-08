"""a pour that did not come out of the tank

Every log written so far is assumed to come off the vessel on that pump
station: the level arithmetic sums what has been logged since the current lot
started and subtracts it. That assumption held while everything on the floor
was filled from a tank.

It stopped holding the day somebody decanted a drum into bottles. The resin
had already left the tank - it left when the drum was filled - so counting the
bottles against the tank as well takes the same litres off twice, and the wall
display shows a vessel emptying that nobody has touched.

So a log can now say it did not come off the tank. The row is production like
any other: it counts toward the shift, the operator's own numbers, the run it
belongs to and every export. The one thing it does not do is move a level.

Zero for every existing row, explicitly rather than left NULL, because every
row written before today did come off the tank and the level figures on the
wall are built from them.

Revision ID: 0018_off_tank_pour
Revises: 0017_device_gateway_toggle
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0018_off_tank_pour"
down_revision = "0017_device_gateway_toggle"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("production_logs",
                  sa.Column("off_tank", sa.Integer(), nullable=True))
    op.execute("UPDATE production_logs SET off_tank = 0 WHERE off_tank IS NULL")


def downgrade():
    op.drop_column("production_logs", "off_tank")
