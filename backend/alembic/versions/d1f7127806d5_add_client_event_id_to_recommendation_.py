"""add client_event_id to recommendation_events

Revision ID: d1f7127806d5
Revises: f475d1becafc
Create Date: 2026-08-25

Backs app/db/models/recommendation_event.py's client_event_id -- a
client-generated idempotency key so a save/unsave outcome resubmitted
after a process-kill-before-persist race (see that column's own
docstring) lands as a harmless no-op instead of a duplicate ledger row.
Mirrors PlaceVideo.client_id's exact same nullable + partial-unique-index
shape for the identical class of problem.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "d1f7127806d5"
down_revision = "f475d1becafc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("recommendation_events")}

    if "client_event_id" not in existing_columns:
        op.add_column(
            "recommendation_events",
            sa.Column("client_event_id", sa.String(length=64), nullable=True),
        )
        op.create_index(
            "uq_recommendation_events_client_event_id",
            "recommendation_events",
            ["client_event_id"],
            unique=True,
            postgresql_where=sa.text("client_event_id IS NOT NULL"),
            sqlite_where=sa.text("client_event_id IS NOT NULL"),
        )


def downgrade() -> None:
    op.drop_index("uq_recommendation_events_client_event_id", table_name="recommendation_events")
    op.drop_column("recommendation_events", "client_event_id")
