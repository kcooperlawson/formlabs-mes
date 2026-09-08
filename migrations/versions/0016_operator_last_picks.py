"""stop making an operator answer the same three questions every hour

The station, the container format and the resin are the same on the second log
of a shift as they were on the first, and on the twelfth. The form asked for
all three every time, so twelve times a shift an operator at a pump was
re-picking answers that had not changed since breakfast.

Remembered against the account rather than the browser, deliberately. A phone
locks, a session drops, a battery dies, somebody picks up a different handset -
and a memory that lives in the tab is gone in every one of those cases, which
are the normal cases on a floor. On the account it follows the person.

Three nullable columns and nothing else. An operator who has never logged has
no last pick, and the form falls back to what it did before.

Revision ID: 0016_operator_last_picks
Revises: 0015_error_reports
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0016_operator_last_picks"
down_revision = "0015_error_reports"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("last_station", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("last_cartridge", sa.String(60), nullable=True))
    op.add_column("users", sa.Column("last_resin", sa.String(100), nullable=True))


def downgrade():
    op.drop_column("users", "last_resin")
    op.drop_column("users", "last_cartridge")
    op.drop_column("users", "last_station")
