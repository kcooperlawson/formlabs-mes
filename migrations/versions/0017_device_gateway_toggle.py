"""a switch for the machine gateway, so it can be offered without being imposed

The gateway has been built since August: six protocols, a poller, a registry
page and a tag map. It has never been connected to real equipment here, so the
page that configures it was left unlinked - reachable only by typing its
address, and listed as a deliberate orphan so the navigation test would not
report it as one.

That is the wrong shape for a thing a plant might genuinely want. Unlinked is
not the same as optional: it means a manager who does want to wire a bench
scale in has no way to find the screen that does it, and no way to know it
exists. So it becomes a setting, like packing and like measured pours - off by
default, and when a plant switches it on the registry appears in the manager's
console where they would look for it.

Off for every existing install, explicitly rather than left NULL for a reader
to interpret. Nothing about the floor changes until somebody decides it should.

Revision ID: 0017_device_gateway_toggle
Revises: 0016_operator_last_picks
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0017_device_gateway_toggle"
down_revision = "0016_operator_last_picks"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("plant_settings",
                  sa.Column("enable_device_gateway", sa.Integer(), nullable=True))
    op.execute("UPDATE plant_settings SET enable_device_gateway = 0 "
               "WHERE enable_device_gateway IS NULL")


def downgrade():
    op.drop_column("plant_settings", "enable_device_gateway")
