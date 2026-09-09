"""a batch in a vessel, so a duration has something to be measured between

Management asked three questions that the system could not answer, and they
are all the same missing thing: when did this resin go to QC, when did it come
back, and how long has it been sitting in that reactor.

A tank's level has always been worked out from the logs rather than stored,
which answers "how much is left" perfectly and cannot answer any of the above.
There was nothing for a duration to be measured between and nothing for a QC
result to be attached to.

So a filling of a vessel is a row now. It opens when a vessel is changed over
to a resin - an event the floor already produces - and closes when the next
changeover happens or somebody says it is empty. The dwell time therefore
starts being right without anybody typing anything new.

The QC times are the exception and are entered by a manager, so they are
nullable and they are free times rather than a stamp of now: the result
usually arrives long before anybody reaches a screen.

Nothing is created by this migration. The application opens a batch per vessel
on its next start, dating each one from that vessel's most recent changeover
where there is one.

Revision ID: 0021_reactor_batches
Revises: 0020_pump_rate_targets
Create Date: 2026-09-09

Numbered 0021 rather than 0020. Two sessions built a migration the same day
and both called it 0020 - this one and the pump rate targets - which gives
Alembic two heads off 0019 and stops the database migrating at all. Renumbered
to follow the one that shipped first.
"""
import sqlalchemy as sa
from alembic import op

revision = "0021_reactor_batches"
down_revision = "0020_pump_rate_targets"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "reactor_batches",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("reactor_name", sa.String(length=100), nullable=False),
        sa.Column("resin_type", sa.String(length=100), nullable=True),
        sa.Column("lot_number", sa.String(length=50), nullable=True),
        sa.Column("pump_station", sa.String(length=50), nullable=True),
        sa.Column("filled_at", sa.DateTime(), nullable=True),
        sa.Column("emptied_at", sa.DateTime(), nullable=True),
        sa.Column("qc_sent_at", sa.DateTime(), nullable=True),
        sa.Column("qc_result_at", sa.DateTime(), nullable=True),
        sa.Column("qc_result", sa.String(length=12), nullable=True),
        sa.Column("qc_note", sa.String(length=240), nullable=True),
        sa.Column("qc_by", sa.String(length=100), nullable=True),
        sa.Column("opened_by", sa.String(length=100), nullable=True),
        sa.Column("closed_by", sa.String(length=100), nullable=True),
        sa.Column("note", sa.String(length=240), nullable=True),
    )
    for column in ("reactor_name", "resin_type", "filled_at", "emptied_at",
                   "qc_sent_at", "qc_result"):
        op.create_index(f"ix_reactor_batches_{column}", "reactor_batches", [column])


def downgrade():
    for column in ("reactor_name", "resin_type", "filled_at", "emptied_at",
                   "qc_sent_at", "qc_result"):
        op.drop_index(f"ix_reactor_batches_{column}", table_name="reactor_batches")
    op.drop_table("reactor_batches")
