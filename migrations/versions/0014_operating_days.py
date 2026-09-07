"""a plant does not run every day, and the alarm did not know

The stopped-record alarm asks the shift clock whether a shift is running, and
the shift clock only ever knew what TIME it was. Every day looked like a
working day - so on a plant that runs Monday to Friday, Saturday at six in the
morning read as Shift 1 running with nothing logged against it, and the wall
display raised an alarm about a weekend. Sunday did it again.

An alarm that cries wolf every weekend is worse than no alarm at all. By
Monday nobody reads the red band, and the one that means something looks
exactly like the fifty that did not.

Seven characters of "1" and "0", Monday first, matching datetime.weekday().
One small column that still reads correctly in a database dump a year from
now and needs no parser to understand.

Defaulted to every day rather than to a working week, deliberately: an
existing install must behave on the day after this migration exactly as it did
on the day before, and a setting that can silence an alarm is not something to
switch on for somebody on the strength of a guess about their shift pattern.
The admin console is where a plant says which days it runs.

Revision ID: 0014_operating_days
Revises: 0013_sheet_targets
Create Date: 2026-09-07
"""
import sqlalchemy as sa
from alembic import op

revision = "0014_operating_days"
down_revision = "0013_sheet_targets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plant_settings",
                  sa.Column("operating_days", sa.String(7), nullable=True))
    op.execute("UPDATE plant_settings SET operating_days = '1111111' "
               "WHERE operating_days IS NULL")


def downgrade() -> None:
    op.drop_column("plant_settings", "operating_days")
