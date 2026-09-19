"""Gateway check-ins, and jobs that run on the gateway PC instead of the server.

gateway_nodes: every PC running run_gateway.py writes a heartbeat here. Until
now nothing did, so when the gateway process died every device kept showing
whatever status it last wrote - "Online", indefinitely - with no way for the
Device Registry to know better.

gateway_jobs: Find Devices and Test Connection used to run inside the API
process, i.e. on whichever PC hosts the MES. On a plant where the machines
are cabled to a separate floor PC, that scanned the wrong network and listed
the wrong COM ports. The page now leaves a job here, the named gateway runs
it where the hardware is, and writes the result back.

Revision ID: 0024_gateway_nodes_and_jobs
Revises: 0023_resin_spec_history
Create Date: 2026-09-16
"""
import sqlalchemy as sa
from alembic import op

revision = "0024_gateway_nodes_and_jobs"
down_revision = "0023_resin_spec_history"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "gateway_nodes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("hostname", sa.String(length=255), nullable=False, unique=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("app_version", sa.String(length=30), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_gateway_nodes_last_heartbeat_at", "gateway_nodes", ["last_heartbeat_at"])

    op.create_table(
        "gateway_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("target_host", sa.String(length=255), nullable=False),
        sa.Column("kind", sa.String(length=30), nullable=False),
        sa.Column("request_json", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("result_json", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_by", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
    )
    op.create_index("ix_gateway_jobs_target_host", "gateway_jobs", ["target_host"])
    op.create_index("ix_gateway_jobs_status", "gateway_jobs", ["status"])


def downgrade():
    op.drop_index("ix_gateway_jobs_status", table_name="gateway_jobs")
    op.drop_index("ix_gateway_jobs_target_host", table_name="gateway_jobs")
    op.drop_table("gateway_jobs")
    op.drop_index("ix_gateway_nodes_last_heartbeat_at", table_name="gateway_nodes")
    op.drop_table("gateway_nodes")
