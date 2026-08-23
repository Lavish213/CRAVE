"""add user_streaks table

Revision ID: z1a2b3c4d5e6
Revises: y1z2a3b4c5d6
Create Date: 2026-08-23

Backs app/db/models/user_streak.py -- the daily-streak gamification
feature (item #4 of the agreed Beli-gap-closing roadmap).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "z1a2b3c4d5e6"
down_revision = "y1z2a3b4c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_streaks" in inspector.get_table_names():
        return

    op.create_table(
        "user_streaks",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=False),
        sa.Column("longest_streak", sa.Integer(), nullable=False),
        sa.Column("last_active_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_user_streaks")),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_streaks" not in inspector.get_table_names():
        return

    op.drop_table("user_streaks")
