"""a sheet somebody can add, instead of a line in a file

The Google export had one destination, set as an environment variable when the
application was installed. Nobody but the installer could point it anywhere; a
second manager who wanted their own sheet could not have one; and when the
variable was missing - which on this copy it was - the page said "webhook
missing" and there was nothing anybody standing in front of it could do.

A destination is a row now. Each one belongs to whoever added it and is
private to them unless they share it, because the point of letting people add
their own is that they do not have to ask for one.

The old environment variable is still read, once, and seeded as a shared
destination named "Plant sheet" if it is set - so an install that was working
keeps working and nobody has to go and find the URL again.

Revision ID: 0013_sheet_targets
Revises: 0012_bulk_pour
Create Date: 2026-09-07
"""
import os

import sqlalchemy as sa
from alembic import op

revision = "0013_sheet_targets"
down_revision = "0012_bulk_pour"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sheet_targets",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("owner_name", sa.String(100), nullable=True),
        sa.Column("is_shared", sa.Integer(), server_default="0"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_status", sa.String(200), nullable=True),
        sa.Column("last_rows", sa.Integer(), nullable=True),
    )

    # Carry the existing destination across rather than losing it. Read from
    # the environment exactly once, here, so that after this migration the
    # variable is history and the row is the truth.
    legacy = (os.getenv("GOOGLE_SHEETS_WEBHOOK") or "").strip()
    if legacy:
        op.execute(sa.text(
            "INSERT INTO sheet_targets (name, webhook_url, owner_name, is_shared, created_at) "
            "VALUES (:n, :u, :o, 1, NOW())"
        ).bindparams(n="Plant sheet", u=legacy, o="Carried over from setup"))


def downgrade() -> None:
    op.drop_table("sheet_targets")
