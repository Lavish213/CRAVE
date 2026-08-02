"""add activity_events table

Written whenever a ranking finalizes or a follow is created; GET
/feed/friends filters these to whoever the caller follows.

Revision ID: t1u2v3w4x5y6
Revises: s1t2u3v4w5x6
Create Date: 2026-08-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "t1u2v3w4x5y6"
down_revision = "s1t2u3v4w5x6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "activity_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("event_type", sa.String(length=32), nullable=False),
        sa.Column("place_id", sa.String(length=36), nullable=True),
        sa.Column("target_user_id", sa.String(length=128), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["place_id"], ["places.id"], name=op.f("fk_activity_events_place_id_places"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_activity_events")),
    )
    with op.batch_alter_table("activity_events", schema=None) as batch_op:
        batch_op.create_index("ix_activity_events_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_activity_events_place_id", ["place_id"], unique=False)
        batch_op.create_index(
            "ix_activity_events_user_created", ["user_id", "created_at"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("activity_events", schema=None) as batch_op:
        batch_op.drop_index("ix_activity_events_user_created")
        batch_op.drop_index("ix_activity_events_place_id")
        batch_op.drop_index("ix_activity_events_user_id")
    op.drop_table("activity_events")
