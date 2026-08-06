"""add failure_count/last_error/next_retry_at to crave_items

Found via a full-app audit of the craves/share system: run_share_parser
only ever selected status='pending' items — a transient fetch failure
('error') or a not-yet-in-the-catalog place ('unmatched') was never
revisited. Same shape as discovery_candidates' existing failure tracking.

Revision ID: w1x2y3z4a5b6
Revises: v1w2x3y4z5a6
Create Date: 2026-08-05
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "w1x2y3z4a5b6"
down_revision = "v1w2x3y4z5a6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("crave_items") as batch_op:
        batch_op.add_column(
            sa.Column(
                "failure_count",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            )
        )
        batch_op.add_column(sa.Column("last_error", sa.String(length=500), nullable=True))
        batch_op.add_column(
            sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.create_index(
            "ix_crave_items_next_retry_at", ["next_retry_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("crave_items") as batch_op:
        batch_op.drop_index("ix_crave_items_next_retry_at")
        batch_op.drop_column("next_retry_at")
        batch_op.drop_column("last_error")
        batch_op.drop_column("failure_count")
