"""startup checklist is per station, not just per day and shift

A pre-shift checklist certifies the condition of the pump the operator is
standing at, so an operator moved to a different pump needs a new one.
Adds `pump_station` / `pump_station_id` to `daily_checklists`.

Both columns are nullable, so rows written before this migration keep
working - has_completed_daily_checklist() treats a NULL station as
satisfying any station for the day it was recorded, which is what stops
this from locking anyone out mid-shift on the day it ships.

Revision ID: 0004_checklist_station
Revises: 0003_lot_verification
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0004_checklist_station"
down_revision = "0003_lot_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("daily_checklists", sa.Column("pump_station", sa.String(50), nullable=True))
    op.add_column("daily_checklists", sa.Column("pump_station_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_daily_checklists_pump_station_id", "daily_checklists",
                          "pump_stations", ["pump_station_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_daily_checklists_pump_station", "daily_checklists", ["pump_station"])
    op.create_index("ix_daily_checklists_pump_station_id", "daily_checklists", ["pump_station_id"])


def downgrade() -> None:
    op.drop_index("ix_daily_checklists_pump_station_id", table_name="daily_checklists")
    op.drop_index("ix_daily_checklists_pump_station", table_name="daily_checklists")
    op.drop_constraint("fk_daily_checklists_pump_station_id", "daily_checklists", type_="foreignkey")
    op.drop_column("daily_checklists", "pump_station_id")
    op.drop_column("daily_checklists", "pump_station")
