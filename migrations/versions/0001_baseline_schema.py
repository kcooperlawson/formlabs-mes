"""baseline schema

This is the starting point for Alembic-managed migrations. It replaces the
old init_db() pattern of Base.metadata.create_all() + a hand-maintained list
of raw ALTER TABLE strings, which had grown to 30+ entries wrapped in a
silent try/except that couldn't distinguish "column already exists" from a
real failure.

This migration reflects the schema as of models.py at the time Alembic was
introduced — every table and column that init_db()'s create_all() + ALTER
TABLE list had already produced. It is meant to be applied two different
ways depending on the database it's running against:

  * A brand-new, empty database (a fresh dev setup, a new plant deployment):
    run `alembic upgrade head` and this migration builds the whole schema
    from scratch.

  * Your existing production database, which already has every one of these
    tables and columns (because init_db() already created them): do NOT run
    `alembic upgrade head` directly — that would try to CREATE TABLE on
    tables that already exist and fail. Instead run `alembic stamp head`
    once. That tells Alembic "the database is already at this revision"
    without touching any tables, and every migration you add after this one
    will apply normally with `alembic upgrade head`.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-08-29
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- Tables with no foreign-key dependencies first ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(50), nullable=False, unique=True),
        sa.Column("email", sa.String(120), nullable=True, unique=True),
        sa.Column("pin", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("target_lph", sa.Float(), nullable=True),
        sa.Column("shift", sa.String(20), nullable=True),
        sa.Column("preferred_theme", sa.String(255), nullable=True),
        sa.Column("avatar_filename", sa.String(255), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_until", sa.DateTime(), nullable=True),
    )

    op.create_table(
        "pump_stations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("station_name", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
    )

    op.create_table(
        "resin_specs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("cartridge_type", sa.String(20), nullable=False),
        sa.Column("sku", sa.String(100), nullable=True),
        sa.Column("resin_code", sa.String(50), nullable=True),
        sa.Column("lifetime_months", sa.String(20), nullable=True),
        sa.Column("resin_name", sa.String(100), nullable=False),
        sa.Column("actual_spec_g", sa.Float(), nullable=False),
        sa.Column("min_weight_g", sa.Float(), nullable=False),
        sa.Column("max_weight_g", sa.Float(), nullable=False),
        sa.Column("acceptable_range", sa.String(50), nullable=True),
        sa.Column("multiplier", sa.Float(), nullable=True),
        sa.Column("color_tag", sa.String(20), nullable=True),
        sa.Column("units_per_skid", sa.Integer(), nullable=True),
    )

    op.create_table(
        "downtime_reasons",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("reason_name", sa.String(100), nullable=False, unique=True),
    )

    op.create_table(
        "plant_settings",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target_lph", sa.Float(), nullable=True),
        sa.Column("packing_target_uph", sa.Float(), nullable=True),
        sa.Column("shift_1_start", sa.String(10), nullable=True),
        sa.Column("shift_1_hours", sa.Float(), nullable=True),
        sa.Column("shift_2_start", sa.String(10), nullable=True),
        sa.Column("shift_2_hours", sa.Float(), nullable=True),
        sa.Column("shift_3_start", sa.String(10), nullable=True),
        sa.Column("shift_3_hours", sa.Float(), nullable=True),
        sa.Column("yield_target_pct", sa.Float(), nullable=True),
        sa.Column("packing_yield_target_pct", sa.Float(), nullable=True),
        sa.Column("shift_1_break_mins", sa.Float(), nullable=True),
        sa.Column("shift_2_break_mins", sa.Float(), nullable=True),
        sa.Column("shift_3_break_mins", sa.Float(), nullable=True),
        sa.Column("handover_emails", sa.Text(), nullable=True),
        sa.Column("enable_packing", sa.Integer(), nullable=True),
    )

    op.create_table(
        "suggestions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("user_name", sa.String(100), nullable=False),
        sa.Column("user_role", sa.String(20), nullable=False),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("suggestion", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("admin_notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_suggestions_timestamp", "suggestions", ["timestamp"])

    op.create_table(
        "user_sessions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("token", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_user_sessions_token", "user_sessions", ["token"])
    op.create_index("ix_user_sessions_user_id", "user_sessions", ["user_id"])

    # --- Tables that reference users / pump_stations / resin_specs ---
    op.create_table(
        "reactors",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("reactor_name", sa.String(100), nullable=False, unique=True),
        sa.Column("max_capacity_l", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("current_resin", sa.String(100), nullable=True),
        sa.Column("assigned_pump", sa.String(50), nullable=True),
        sa.Column("current_resin_id", sa.Integer(),
                  sa.ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assigned_pump_id", sa.Integer(),
                  sa.ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True),
    )
    op.create_index("ix_reactors_current_resin_id", "reactors", ["current_resin_id"])
    op.create_index("ix_reactors_assigned_pump_id", "reactors", ["assigned_pump_id"])

    op.create_table(
        "production_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("log_type", sa.String(50), nullable=False),
        sa.Column("operator_name", sa.String(100), nullable=False),
        sa.Column("pump_station", sa.String(50), nullable=False),
        sa.Column("operator_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pump_station_id", sa.Integer(),
                  sa.ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resin_spec_id", sa.Integer(),
                  sa.ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shift", sa.String(20), nullable=True),
        sa.Column("cartridge_type", sa.String(20), nullable=True),
        sa.Column("resin_type", sa.String(100), nullable=True),
        sa.Column("lot_number", sa.String(50), nullable=True),
        sa.Column("bottles_filled", sa.Integer(), nullable=True),
        sa.Column("scrap_empty", sa.Integer(), nullable=True),
        sa.Column("scrap_filled", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_production_logs_timestamp", "production_logs", ["timestamp"])
    op.create_index("ix_production_logs_date", "production_logs", ["date"])
    op.create_index("ix_production_logs_operator_name", "production_logs", ["operator_name"])
    op.create_index("ix_production_logs_pump_station", "production_logs", ["pump_station"])
    op.create_index("ix_production_logs_operator_id", "production_logs", ["operator_id"])
    op.create_index("ix_production_logs_pump_station_id", "production_logs", ["pump_station_id"])
    op.create_index("ix_production_logs_resin_spec_id", "production_logs", ["resin_spec_id"])

    op.create_table(
        "downtime_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("operator_name", sa.String(100), nullable=False),
        sa.Column("pump_station", sa.String(50), nullable=False),
        sa.Column("operator_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pump_station_id", sa.Integer(),
                  sa.ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shift", sa.String(20), nullable=True),
        sa.Column("reason", sa.String(100), nullable=False),
        sa.Column("duration_min", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_downtime_logs_timestamp", "downtime_logs", ["timestamp"])
    op.create_index("ix_downtime_logs_date", "downtime_logs", ["date"])
    op.create_index("ix_downtime_logs_operator_id", "downtime_logs", ["operator_id"])
    op.create_index("ix_downtime_logs_pump_station_id", "downtime_logs", ["pump_station_id"])

    op.create_table(
        "assigned_runs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("reactor_id", sa.String(50), nullable=True),
        sa.Column("reactor_size_l", sa.Integer(), nullable=True),
        sa.Column("resin_type", sa.String(100), nullable=False),
        sa.Column("cartridge_type", sa.String(20), nullable=True),
        sa.Column("target_units", sa.Integer(), nullable=False),
        sa.Column("current_units", sa.Integer(), nullable=True),
        sa.Column("assigned_operator", sa.String(100), nullable=False),
        sa.Column("pump_station", sa.String(50), nullable=False),
        sa.Column("resin_spec_id", sa.Integer(),
                  sa.ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("operator_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pump_station_id", sa.Integer(),
                  sa.ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=True),
        sa.Column("lot_number", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("run_type", sa.String(20), nullable=True),
    )
    op.create_index("ix_assigned_runs_resin_spec_id", "assigned_runs", ["resin_spec_id"])
    op.create_index("ix_assigned_runs_operator_id", "assigned_runs", ["operator_id"])
    op.create_index("ix_assigned_runs_pump_station_id", "assigned_runs", ["pump_station_id"])

    op.create_table(
        "daily_checklists",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("operator_name", sa.String(100), nullable=False),
        sa.Column("operator_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shift", sa.String(20), nullable=False),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_daily_checklists_date", "daily_checklists", ["date"])
    op.create_index("ix_daily_checklists_operator_name", "daily_checklists", ["operator_name"])
    op.create_index("ix_daily_checklists_operator_id", "daily_checklists", ["operator_id"])

    op.create_table(
        "cleanliness_audits",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("date", sa.Date(), nullable=True),
        sa.Column("audit_type", sa.String(50), nullable=False),
        sa.Column("operator_name", sa.String(100), nullable=False),
        sa.Column("pump_station", sa.String(50), nullable=False),
        sa.Column("operator_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("pump_station_id", sa.Integer(),
                  sa.ForeignKey("pump_stations.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resin_spec_id", sa.Integer(),
                  sa.ForeignKey("resin_specs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("shift", sa.String(20), nullable=True),
        sa.Column("resin_type", sa.String(100), nullable=True),
        sa.Column("image_filename", sa.String(255), nullable=True),
        sa.Column("is_spill", sa.String(10), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
    )
    op.create_index("ix_cleanliness_audits_timestamp", "cleanliness_audits", ["timestamp"])
    op.create_index("ix_cleanliness_audits_date", "cleanliness_audits", ["date"])
    op.create_index("ix_cleanliness_audits_operator_id", "cleanliness_audits", ["operator_id"])
    op.create_index("ix_cleanliness_audits_pump_station_id", "cleanliness_audits", ["pump_station_id"])
    op.create_index("ix_cleanliness_audits_resin_spec_id", "cleanliness_audits", ["resin_spec_id"])

    op.create_table(
        "floor_messages",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("timestamp", sa.DateTime(), nullable=True),
        sa.Column("operator_name", sa.String(100), nullable=False),
        sa.Column("sender_name", sa.String(100), nullable=False),
        sa.Column("operator_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_id", sa.Integer(),
                  sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_manager_reply", sa.Integer(), nullable=True),
    )
    op.create_index("ix_floor_messages_timestamp", "floor_messages", ["timestamp"])
    op.create_index("ix_floor_messages_operator_name", "floor_messages", ["operator_name"])
    op.create_index("ix_floor_messages_operator_id", "floor_messages", ["operator_id"])
    op.create_index("ix_floor_messages_sender_id", "floor_messages", ["sender_id"])


def downgrade() -> None:
    # Drop in reverse dependency order.
    op.drop_table("floor_messages")
    op.drop_table("cleanliness_audits")
    op.drop_table("daily_checklists")
    op.drop_table("assigned_runs")
    op.drop_table("downtime_logs")
    op.drop_table("production_logs")
    op.drop_table("reactors")
    op.drop_table("user_sessions")
    op.drop_table("suggestions")
    op.drop_table("plant_settings")
    op.drop_table("downtime_reasons")
    op.drop_table("resin_specs")
    op.drop_table("pump_stations")
    op.drop_table("users")
