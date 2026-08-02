"""add place_rankings table

A user's personal, comparison-derived ranking of a visited place — see
app.services.ranking.ranking_service for the binary-insertion algorithm
that produces rank_score. Reverse-engineered from Beli's own "which was
better" mechanic (see PR description / session notes for the research).

Revision ID: s1t2u3v4w5x6
Revises: r1s2t3u4v5w6
Create Date: 2026-08-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "s1t2u3v4w5x6"
down_revision = "r1s2t3u4v5w6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "place_rankings",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=128), nullable=False),
        sa.Column("place_id", sa.String(length=36), nullable=False),
        sa.Column("tier", sa.String(length=16), nullable=False),
        sa.Column("rank_score", sa.Float(), nullable=False),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "tier in ('liked', 'fine', 'disliked')", name=op.f("ck_place_rankings_valid_tier")
        ),
        sa.ForeignKeyConstraint(
            ["place_id"], ["places.id"], name=op.f("fk_place_rankings_place_id_places"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_place_rankings")),
        sa.UniqueConstraint("user_id", "place_id", name="uq_place_rankings_user_place"),
    )
    with op.batch_alter_table("place_rankings", schema=None) as batch_op:
        batch_op.create_index("ix_place_rankings_user_id", ["user_id"], unique=False)
        batch_op.create_index("ix_place_rankings_place_id", ["place_id"], unique=False)
        batch_op.create_index(
            "ix_place_rankings_user_tier_score", ["user_id", "tier", "rank_score"], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table("place_rankings", schema=None) as batch_op:
        batch_op.drop_index("ix_place_rankings_user_tier_score")
        batch_op.drop_index("ix_place_rankings_place_id")
        batch_op.drop_index("ix_place_rankings_user_id")
    op.drop_table("place_rankings")
