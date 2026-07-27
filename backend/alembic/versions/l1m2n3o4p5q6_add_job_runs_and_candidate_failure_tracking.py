"""add job_runs table and discovery_candidates failure tracking columns

Revision ID: l1m2n3o4p5q6
Revises: k1l2m3n4o5p6
Create Date: 2026-07-26

Two independent additions bundled into one migration, both closing the same
class of gap: the ingestion pipeline previously had no failure visibility.

1. job_runs — one row per scheduled-job execution (app/scheduler.py), written
   by app/core/job_run_tracker.py. Before this, jobs logged one stdout line
   and left no queryable record of what ran or what it did.

2. discovery_candidates.failure_count / last_error / next_retry_at — before
   this, a permanently-broken candidate was retried by the discovery
   scheduler job forever with no record of why, since promotion failures
   were caught and silently discarded (see
   app/services/discovery/promotion_orchestrator_v2.py).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "l1m2n3o4p5q6"
down_revision = "k1l2m3n4o5p6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "job_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_name", sa.String(64), nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("ix_job_runs_job_name", "job_runs", ["job_name"])
    op.create_index(
        "ix_job_runs_job_name_started", "job_runs", ["job_name", "started_at"]
    )

    with op.batch_alter_table("discovery_candidates") as batch_op:
        batch_op.add_column(
            sa.Column(
                "failure_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(sa.Column("last_error", sa.String(500), nullable=True))
        batch_op.add_column(
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index("ix_candidate_next_retry_at", ["next_retry_at"])


def downgrade() -> None:
    with op.batch_alter_table("discovery_candidates") as batch_op:
        batch_op.drop_index("ix_candidate_next_retry_at")
        batch_op.drop_column("next_retry_at")
        batch_op.drop_column("last_error")
        batch_op.drop_column("failure_count")

    op.drop_index("ix_job_runs_job_name_started", table_name="job_runs")
    op.drop_index("ix_job_runs_job_name", table_name="job_runs")
    op.drop_table("job_runs")
