"""hold the external pump form's address as a setting, not in source

There is a QR sticker on the pump that opens a form somebody outside this
application owns. Scanning it works, but it is a one-way trip: the phone
leaves whatever the operator was doing and the way back is the browser's
back button, which on a Streamlit app costs the session.

A link opened from inside the MES avoids that entirely - the MES tab is
never navigated away from, the form opens alongside it, and closing the form
puts the operator back exactly where they were. That is strictly better than
walking to the pump to scan a sticker, and it is the same destination.

The address is a setting rather than a constant because the application does
not own that form. Whoever does can move it, and moving it should cost an
admin one field, not a code change and a redeploy. Both columns are nullable
with no default on purpose: an install that has not been told about a form
shows no button at all, which is the correct behaviour for a plant that
does not have one.

Revision ID: 0008_pump_form_url
Revises: 0007_shift_count
Create Date: 2026-09-02
"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "0008_pump_form_url"
down_revision = "0007_shift_count"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("plant_settings", sa.Column("pump_form_url", sa.Text(), nullable=True))
    op.add_column("plant_settings", sa.Column("pump_form_label", sa.String(length=60), nullable=True))


def downgrade() -> None:
    op.drop_column("plant_settings", "pump_form_label")
    op.drop_column("plant_settings", "pump_form_url")
