"""the shift handover is gone, and so is the address list it needed

The handover screen produced a PDF of four whole-day figures - poured,
packed, work in progress, scrap - and emailed it to this list. Every one of
those numbers is on the landing screen, broken down by station, operator,
resin and shift, which the PDF was not: it filtered by date rather than by
shift, so on a two-shift plant the second shift's "handover" silently
included the first shift's work. The incoming lead, who arrives before the
shift and opens the app, was always going to see more than the report.

It was also the only feature in the application that needed an outside
credential - an email account and password, and outbound SMTP from a floor
PC - which made the least useful screen the most expensive one to set up.

Dropping the column rather than leaving it: a settings field that no screen
reads and no screen writes is worse than no field. It comes back with the
feature if the feature ever comes back, and re-adding a nullable text column
is the same one-line migration in the other direction.

Revision ID: 0010_drop_handover_emails
Revises: 0009_simple_mode
Create Date: 2026-09-04
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0010_drop_handover_emails"
down_revision = "0009_simple_mode"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("plant_settings", "handover_emails")


def downgrade() -> None:
    op.add_column("plant_settings", sa.Column("handover_emails", sa.Text(), nullable=True))
