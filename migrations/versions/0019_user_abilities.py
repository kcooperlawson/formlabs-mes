"""abilities handed to one account, on top of what its role gives

A role is a starting point, not a description of a person. The floor has an
operator who built this system and needs screens no operator needs, and the
answer to that should not be to make him a manager in every report he appears
in. It should be to say that this account can also do these things.

Rows rather than a column of flags, so the history is the record. A revoked
grant keeps its row with who revoked it and when, because the first question
anyone asks about a permission is how somebody came to have it. Active grants
are the rows with no revoked_at.

Nothing is granted by this migration. Every account keeps exactly what its
role gave it until somebody deliberately ticks a box.

Revision ID: 0019_user_abilities
Revises: 0018_off_tank_pour
Create Date: 2026-09-09
"""
import sqlalchemy as sa
from alembic import op

revision = "0019_user_abilities"
down_revision = "0018_off_tank_pour"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "user_abilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("ability", sa.String(length=40), nullable=False),
        sa.Column("granted_by", sa.String(length=100), nullable=True),
        sa.Column("granted_at", sa.DateTime(), nullable=True),
        sa.Column("revoked_by", sa.String(length=100), nullable=True),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_user_abilities_user_id", "user_abilities", ["user_id"])
    op.create_index("ix_user_abilities_ability", "user_abilities", ["ability"])
    op.create_index("ix_user_abilities_revoked_at", "user_abilities", ["revoked_at"])


def downgrade():
    op.drop_index("ix_user_abilities_revoked_at", table_name="user_abilities")
    op.drop_index("ix_user_abilities_ability", table_name="user_abilities")
    op.drop_index("ix_user_abilities_user_id", table_name="user_abilities")
    op.drop_table("user_abilities")
