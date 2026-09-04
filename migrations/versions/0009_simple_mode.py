"""a plant can run this as a log and nothing else

The application grew work orders early, so every screen assumes somebody
upstream dispatched a run and the operator is logging against it. That is a
real way to run a plant. It is not the only one, and it is not the one a
plant starts in: on day one nobody has entered anything, and an operator
pouring a cartridge still has something worth recording.

Without this column the app has no way to tell "nobody has set this up yet"
apart from "this plant does not work that way", so it treats both as the
first and asks the operator to go find a manager. Simple mode is that
distinction, stored. On, the operator form is a log: pick the station and
material, read the lot, enter the counts. Off, the work-order screens come
back exactly as they were.

Server default 1, including for the row that already exists. A plant that
wants dispatch turns it on deliberately, which is the right direction for a
default to point - the setting a plant never finds should be the smaller
one.

Revision ID: 0009_simple_mode
Revises: 0008_pump_form_url
Create Date: 2026-09-03
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0009_simple_mode"
down_revision = "0008_pump_form_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plant_settings",
                  sa.Column("simple_mode", sa.Integer(), nullable=False,
                            server_default="1"))


def downgrade() -> None:
    op.drop_column("plant_settings", "simple_mode")
