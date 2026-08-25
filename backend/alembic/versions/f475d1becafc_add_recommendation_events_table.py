"""add recommendation_events table

Revision ID: f475d1becafc
Revises: df7061f16615
Create Date: 2026-08-25

Backs app/db/models/recommendation_event.py -- Recommendation Ledger
phase 1 (see that module's docstring): logs which surface showed a
place, at what position/percentile, and what the user did about it.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f475d1becafc"
down_revision = "df7061f16615"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "recommendation_events" not in existing_tables:
        op.create_table(
            "recommendation_events",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.String(length=128), nullable=True),
            sa.Column("session_id", sa.String(length=64), nullable=True),
            sa.Column("place_id", sa.String(length=36), nullable=True),
            sa.Column("surface", sa.String(length=16), nullable=False),
            sa.Column("event_type", sa.String(length=16), nullable=False),
            sa.Column("position", sa.Integer(), nullable=True),
            sa.Column("rank_percentile", sa.Float(), nullable=True),
            sa.Column("query", sa.String(length=200), nullable=True),
            sa.Column("city_id", sa.String(length=36), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["place_id"], ["places.id"],
                name=op.f("fk_recommendation_events_place_id_places"),
                ondelete="SET NULL",
            ),
            sa.PrimaryKeyConstraint("id", name=op.f("pk_recommendation_events")),
        )
        op.create_index(
            "ix_recommendation_events_user_created",
            "recommendation_events",
            ["user_id", "created_at"],
        )
        op.create_index(
            "ix_recommendation_events_place_id",
            "recommendation_events",
            ["place_id"],
        )
        op.create_index(
            "ix_recommendation_events_surface_type",
            "recommendation_events",
            ["surface", "event_type"],
        )


def downgrade() -> None:
    op.drop_table("recommendation_events")
