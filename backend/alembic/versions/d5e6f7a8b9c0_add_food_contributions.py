"""add food contributions

Revision ID: d5e6f7a8b9c0
Revises: c4d5e6f7a8b9
Create Date: 2026-09-09
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d5e6f7a8b9c0"
down_revision = "c4d5e6f7a8b9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "food_contributions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("client_id", sa.String(length=64), nullable=False),
        sa.Column("place_id", sa.String(length=36), nullable=False),
        sa.Column("intent", sa.String(length=24), nullable=False),
        sa.Column("reaction", sa.String(length=24), nullable=True),
        sa.Column("caption", sa.Text(), nullable=True),
        sa.Column("visibility", sa.String(length=24), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("image_id", sa.String(length=36), nullable=True),
        sa.Column("video_id", sa.String(length=36), nullable=True),
        sa.Column("status", sa.String(length=24), server_default="committed", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["image_id"], ["place_images.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["place_id"], ["places.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["video_id"], ["place_videos.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_food_contributions")),
    )
    op.create_index("ix_food_contributions_user_created", "food_contributions", ["user_id", "created_at"])
    op.create_index("ix_food_contributions_place_created", "food_contributions", ["place_id", "created_at"])
    op.create_index("ix_food_contributions_visibility_created", "food_contributions", ["visibility", "created_at"])
    op.create_index("uq_food_contributions_user_client_id", "food_contributions", ["user_id", "client_id"], unique=True)


def downgrade() -> None:
    op.drop_table("food_contributions")
