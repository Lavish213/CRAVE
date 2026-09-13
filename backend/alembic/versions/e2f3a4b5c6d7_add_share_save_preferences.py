"""preserve explicit unsaves for matched social shares

Revision ID: e2f3a4b5c6d7
Revises: c4d5e6f7a8b9
Create Date: 2026-09-12
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e2f3a4b5c6d7"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "share_save_preferences",
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("place_id", sa.String(length=36), nullable=False),
        sa.Column("opted_out_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "place_id"),
    )


def downgrade() -> None:
    op.drop_table("share_save_preferences")
