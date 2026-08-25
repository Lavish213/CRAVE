"""add search_session_id to recommendation_events

Revision ID: f8a2c6d90e13
Revises: d1f7127806d5
Create Date: 2026-08-25

Backs app/db/models/recommendation_event.py's search_session_id --
a single search interaction session, narrower than the existing
session_id (which spans a whole app launch). Lets a later analysis
reconstruct query -> results shown -> selection -> reformulation for
Search instrumentation without inventing a separate logged
"reformulated" event.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f8a2c6d90e13"
down_revision = "d1f7127806d5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("recommendation_events")}

    if "search_session_id" not in existing_columns:
        op.add_column(
            "recommendation_events",
            sa.Column("search_session_id", sa.String(length=64), nullable=True),
        )
        op.create_index(
            "ix_recommendation_events_search_session",
            "recommendation_events",
            ["search_session_id"],
        )


def downgrade() -> None:
    op.drop_index("ix_recommendation_events_search_session", table_name="recommendation_events")
    op.drop_column("recommendation_events", "search_session_id")
