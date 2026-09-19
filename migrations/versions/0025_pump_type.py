"""What kind of pump each station is.

Piston diaphragm and electric motor pumps behave nothing alike - the old
piston pumps run at a fraction of the rate the newer motor pumps do - and
until now the application had no idea which was which. Every number it
showed about a pump had to be either configured by hand or inferred from
that pump's own history.

Nullable on purpose: existing stations are whatever they already were, and
nobody has to go and label them before anything works.

Revision ID: 0025_pump_type
Revises: 0024_gateway_nodes_and_jobs
Create Date: 2026-09-18
"""
import sqlalchemy as sa
from alembic import op

revision = "0025_pump_type"
down_revision = "0024_gateway_nodes_and_jobs"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("pump_stations", sa.Column("pump_type", sa.String(length=30), nullable=True))


def downgrade():
    op.drop_column("pump_stations", "pump_type")
