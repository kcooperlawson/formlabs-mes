"""not everything that leaves a tank is a cartridge

The record could only say how many containers were filled, and worked the
volume out by multiplying that by a fixed size per format: a V2 is one litre,
an RPS jug is five. That is true of everything that goes down a line, and it
is exactly wrong for the pours that do not - a specific amount decanted into
a drum, a tote, a pail. There was no way to write "we put 180 litres into a
drum" down, so it either went in as a wrong number of cartridges or it did
not go in at all, and either way the tank it came out of was wrong from that
moment on.

Two columns, both optional:

  litres_poured is the volume when the volume is known directly. When it is
  set it IS the amount, and the count-times-format arithmetic is not
  consulted. NULL on every row that exists today and on every ordinary
  cartridge log after this, so nothing that has already been recorded changes
  meaning and every existing query keeps returning what it returned before.

  pour_note carries what it was poured into, in the operator's own words -
  "55 gal drum", "blue tote". The application does not parse it and does not
  need to; it is there so the row can be read a year later by somebody
  reconciling a tank, which is the only reason anybody opens a log that old.

The plant setting is deliberately off. A floor that never does this should
not have to look at a control for it, and the operator's form is identical
until somebody turns it on.

Revision ID: 0012_bulk_pour
Revises: 0011_vessel_identity
Create Date: 2026-09-07
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0012_bulk_pour"
down_revision = "0011_vessel_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("production_logs", sa.Column("litres_poured", sa.Float(), nullable=True))
    op.add_column("production_logs", sa.Column("pour_note", sa.String(120), nullable=True))
    op.add_column("plant_settings", sa.Column("enable_bulk_pour", sa.Integer(), nullable=True))

    # Off, explicitly, rather than left NULL for the reader to interpret.
    op.execute("UPDATE plant_settings SET enable_bulk_pour = 0 WHERE enable_bulk_pour IS NULL")


def downgrade() -> None:
    op.drop_column("plant_settings", "enable_bulk_pour")
    op.drop_column("production_logs", "pour_note")
    op.drop_column("production_logs", "litres_poured")
