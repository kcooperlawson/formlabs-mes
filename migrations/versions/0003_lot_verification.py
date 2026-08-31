"""cartridge lot verification gate

Adds `lot_verifications` (one row per cartridge-lot check performed at the
pouring station, passes and failures alike) and a denormalized
`production_logs.verify_status` column so dashboards can filter logs by
verification outcome without a join.

Purely additive - no existing column is altered or dropped, and
verify_status is nullable so every pre-existing production log stays valid.

Revision ID: 0003_lot_verification
Revises: 0002_device_gateway
Create Date: 2026-08-31
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0003_lot_verification"
down_revision = "0002_device_gateway"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "lot_verifications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("operator_name", sa.String(100), nullable=False),
        sa.Column("operator_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pump_station", sa.String(50), nullable=False),
        sa.Column("pump_station_id", sa.Integer(),
                  sa.ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shift", sa.String(20), nullable=True, server_default="Shift 1"),
        sa.Column("cartridge_type", sa.String(20), nullable=True, server_default="V2"),
        sa.Column("resin_type", sa.String(100), nullable=True),
        sa.Column("resin_spec_id", sa.Integer(),
                  sa.ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("expected_lot", sa.String(50), nullable=True),
        sa.Column("entered_lot", sa.String(50), nullable=True),
        sa.Column("entered_expiry", sa.String(20), nullable=True),
        sa.Column("expiry_status", sa.String(20), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("check_level", sa.String(20), nullable=True, server_default="full"),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("photo_filename", sa.String(255), nullable=True),
        sa.Column("ocr_lot", sa.String(50), nullable=True),
        sa.Column("ocr_conflict", sa.Integer(), nullable=True, server_default="0"),
        sa.Column("production_log_id", sa.Integer(),
                  sa.ForeignKey("production_logs.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_lot_verifications_timestamp", "lot_verifications", ["timestamp"])
    op.create_index("ix_lot_verifications_date", "lot_verifications", ["date"])
    op.create_index("ix_lot_verifications_operator_name", "lot_verifications", ["operator_name"])
    op.create_index("ix_lot_verifications_operator_id", "lot_verifications", ["operator_id"])
    op.create_index("ix_lot_verifications_pump_station", "lot_verifications", ["pump_station"])
    op.create_index("ix_lot_verifications_pump_station_id", "lot_verifications", ["pump_station_id"])
    op.create_index("ix_lot_verifications_resin_spec_id", "lot_verifications", ["resin_spec_id"])
    op.create_index("ix_lot_verifications_result", "lot_verifications", ["result"])
    op.create_index("ix_lot_verifications_production_log_id", "lot_verifications", ["production_log_id"])

    op.add_column("production_logs", sa.Column("verify_status", sa.String(20), nullable=True))
    op.create_index("ix_production_logs_verify_status", "production_logs", ["verify_status"])


def downgrade() -> None:
    op.drop_index("ix_production_logs_verify_status", table_name="production_logs")
    op.drop_column("production_logs", "verify_status")

    for ix in (
        "ix_lot_verifications_production_log_id",
        "ix_lot_verifications_result",
        "ix_lot_verifications_resin_spec_id",
        "ix_lot_verifications_pump_station_id",
        "ix_lot_verifications_pump_station",
        "ix_lot_verifications_operator_id",
        "ix_lot_verifications_operator_name",
        "ix_lot_verifications_date",
        "ix_lot_verifications_timestamp",
    ):
        op.drop_index(ix, table_name="lot_verifications")
    op.drop_table("lot_verifications")
