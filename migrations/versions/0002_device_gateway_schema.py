"""device gateway schema

Adds the three tables behind the Device Gateway: `devices` (one row per
floor machine, whatever protocol it speaks), `device_tag_maps` (raw tag ->
canonical metric mapping per device), and `device_readings` (append-only
raw telemetry). Purely additive — no existing table is touched.

Revision ID: 0002_device_gateway
Revises: 0001_baseline
Create Date: 2026-08-30
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0002_device_gateway"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "devices",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_name", sa.String(100), nullable=False, unique=True),
        sa.Column("device_role", sa.String(30), nullable=False, server_default="filling_station"),
        sa.Column("protocol", sa.String(30), nullable=False),
        sa.Column("connection_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("poll_interval_s", sa.Float(), nullable=True, server_default="5"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("pump_station_id", sa.Integer(),
                  sa.ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reactor_id", sa.Integer(),
                  sa.ForeignKey("reactors.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=True, server_default="Unknown"),
        sa.Column("last_seen_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_devices_pump_station_id", "devices", ["pump_station_id"])
    op.create_index("ix_devices_reactor_id", "devices", ["reactor_id"])

    op.create_table(
        "device_tag_maps",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("raw_tag", sa.String(255), nullable=False),
        sa.Column("canonical_metric", sa.String(50), nullable=False),
        sa.Column("data_type", sa.String(20), nullable=True, server_default="float"),
        sa.Column("scale_factor", sa.Float(), nullable=True, server_default="1"),
        sa.Column("unit", sa.String(20), nullable=True),
    )
    op.create_index("ix_device_tag_maps_device_id", "device_tag_maps", ["device_id"])

    op.create_table(
        "device_readings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("device_id", sa.Integer(),
                  sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("metric", sa.String(50), nullable=False),
        sa.Column("value_numeric", sa.Float(), nullable=True),
        sa.Column("value_text", sa.String(255), nullable=True),
    )
    op.create_index("ix_device_readings_device_id", "device_readings", ["device_id"])
    op.create_index("ix_device_readings_timestamp", "device_readings", ["timestamp"])
    op.create_index("ix_device_readings_metric", "device_readings", ["metric"])


def downgrade() -> None:
    op.drop_table("device_readings")
    op.drop_table("device_tag_maps")
    op.drop_table("devices")
