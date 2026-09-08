"""somewhere for a crash to go, other than a log file nobody opens

Floor terminals are configured not to show tracebacks, which is right. The
consequence was that a page breaking produced a generic red box for whoever was
standing there, a line in a log file on the plant PC, and no way for anybody
else to find out. Whether a bug got reported depended on a manager remembering,
three days later, that a screen went funny.

This is the table those land in instead: the page, who was on it, their role,
the app version, the real traceback, and a short reference code the person can
quote. It is a record of faults, not of production, so it is deliberately its
own table - a crash is not a log row and must never be countable as one.

`ref_code` is derived from the fault rather than random, so the same break
gives the same code every time and three managers reporting K7F2 are visibly
reporting one bug. Indexed because that is what somebody types in to find it.

Nothing here is required. An install that never crashes has an empty table.

Revision ID: 0015_error_reports
Revises: 0014_operating_days
Create Date: 2026-09-08
"""
import sqlalchemy as sa
from alembic import op

revision = "0015_error_reports"
down_revision = "0014_operating_days"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "error_reports",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("occurred_at", sa.DateTime, nullable=False, index=True),
        # Short, spoken out loud, and stable for a given fault.
        sa.Column("ref_code", sa.String(12), nullable=False, index=True),
        sa.Column("page", sa.String(120), nullable=True),
        # The name as it was at the time, not a link. A crash report has to
        # still make sense after somebody leaves, and it must never be the
        # thing that stops a user record being deleted.
        sa.Column("user_name", sa.String(120), nullable=True),
        sa.Column("user_role", sa.String(40), nullable=True),
        sa.Column("app_version", sa.String(40), nullable=True),
        sa.Column("error_type", sa.String(120), nullable=True),
        sa.Column("message", sa.Text, nullable=True),
        sa.Column("traceback", sa.Text, nullable=True),
        # How many times this same fault has been seen. One row per kind
        # rather than per occurrence: a page that breaks on every refresh
        # would otherwise write a row every ten seconds all afternoon and
        # bury the other faults under it.
        sa.Column("hits", sa.Integer, nullable=False, server_default="1"),
        sa.Column("last_seen_at", sa.DateTime, nullable=True),
        sa.Column("resolved", sa.Integer, nullable=False, server_default="0"),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        sa.Column("resolved_by", sa.String(120), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
    )


def downgrade():
    op.drop_table("error_reports")
