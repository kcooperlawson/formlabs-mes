"""The resin spec audit trail table was never created.

models.py has carried a ResinSpecHistory model since the resin colour work,
and crud.py's add_resin_spec/bulk_update_resin_specs/delete_resin_spec all
call _log_resin_spec_history() on every write - but no migration ever
created resin_spec_history itself. The result: every add, edit, and delete
of a resin specification has been failing outright (add_resin_spec/
delete_resin_spec catch the exception and return False; the page then shows
a misleading "check for duplicate names" or just silently doesn't update),
on every environment, including production, since the day that model was
added. Found while porting Mgr_Resin_Canvas.py's add/edit/delete flows to
the new API - the exact same crud.py functions the Streamlit page has
always called.

resin_spec_id deliberately has no foreign key: the model's own docstring
says the id is "kept even after the spec is deleted so the trail still
points at the right row in time", which a FK would prevent.

Revision ID: 0023_resin_spec_history
Revises: 0022_cleanliness_audit_photos
Create Date: 2026-09-13
"""
import sqlalchemy as sa
from alembic import op

revision = "0023_resin_spec_history"
down_revision = "0022_cleanliness_audit_photos"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "resin_spec_history",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("resin_spec_id", sa.Integer(), nullable=True),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("changed_by", sa.String(length=100), nullable=True),
        sa.Column("changed_at", sa.DateTime(), nullable=True),
        sa.Column("old_values", sa.Text(), nullable=True),
        sa.Column("new_values", sa.Text(), nullable=True),
    )
    op.create_index("ix_resin_spec_history_resin_spec_id", "resin_spec_history", ["resin_spec_id"])
    op.create_index("ix_resin_spec_history_changed_at", "resin_spec_history", ["changed_at"])


def downgrade():
    op.drop_index("ix_resin_spec_history_changed_at", table_name="resin_spec_history")
    op.drop_index("ix_resin_spec_history_resin_spec_id", table_name="resin_spec_history")
    op.drop_table("resin_spec_history")
