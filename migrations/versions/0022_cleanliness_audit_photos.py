"""An audit is allowed more than one photo.

One photo was enough to prove the station was checked and not enough to
document how it was checked. A spill has the puddle, the absorbent, and the
containment. A changeover has the last resin in the nozzle and the first in
the new one. One frame cannot hold all of that, and cropping the scene to
fit the frame is worse than useless.

So the first photo stays in the column every reader already looks at
(image_filename) - the gallery, the exports, and every row written before
this existed are untouched - and the extras hang on their own table, one row
per photo in upload order, leaving with their audit through the foreign key.

Nothing is created by this migration. Audits pick up extra photos the next
time an operator attaches them.

Revision ID: 0022_cleanliness_audit_photos
Revises: 0021_reactor_batches
Create Date: 2026-09-10
"""
import sqlalchemy as sa
from alembic import op

revision = "0022_cleanliness_audit_photos"
down_revision = "0021_reactor_batches"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "cleanliness_audit_photos",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("audit_id", sa.Integer(),
                  sa.ForeignKey("cleanliness_audits.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("note", sa.String(length=240), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_cleanliness_audit_photos_audit_id", "cleanliness_audit_photos", ["audit_id"])


def downgrade():
    op.drop_index("ix_cleanliness_audit_photos_audit_id", table_name="cleanliness_audit_photos")
    op.drop_table("cleanliness_audit_photos")
