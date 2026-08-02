"""add user_follows table

The friend graph. Nothing social (feed, leaderboard, place-level friend
score) means anything without this existing first.

Revision ID: r1s2t3u4v5w6
Revises: q1r2s3t4u5v6
Create Date: 2026-08-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r1s2t3u4v5w6"
down_revision = "q1r2s3t4u5v6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_follows",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("follower_id", sa.String(length=128), nullable=False),
        sa.Column("followee_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "follower_id != followee_id", name=op.f("ck_user_follows_no_self_follow")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_follows")),
        sa.UniqueConstraint("follower_id", "followee_id", name="uq_user_follows_pair"),
    )
    with op.batch_alter_table("user_follows", schema=None) as batch_op:
        batch_op.create_index("ix_user_follows_follower", ["follower_id"], unique=False)
        batch_op.create_index("ix_user_follows_followee", ["followee_id"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("user_follows", schema=None) as batch_op:
        batch_op.drop_index("ix_user_follows_followee")
        batch_op.drop_index("ix_user_follows_follower")
    op.drop_table("user_follows")
