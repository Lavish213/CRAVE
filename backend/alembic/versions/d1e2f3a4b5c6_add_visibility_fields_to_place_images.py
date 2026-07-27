"""add visibility_status, quality_score, content_type to place_images

Revision ID: d1e2f3a4b5c6
Revises: c1d2e3f4a5b6
Create Date: 2026-04-22

Phase 1 — State Foundation.
Adds the three required fields for the CRAVE visibility system.
Existing ingested images default to gallery_only (safe — pipeline already filtered them).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "d1e2f3a4b5c6"
down_revision = "c1d2e3f4a5b6"
branch_labels = None
depends_on = None

# Valid visibility states (kept as strings — no enum in DB to avoid migration pain)
_VISIBILITY_DEFAULT = "gallery_only"


def upgrade() -> None:
    with op.batch_alter_table("place_images") as batch_op:
        batch_op.add_column(
            sa.Column(
                "visibility_status",
                sa.String(32),
                nullable=False,
                server_default=_VISIBILITY_DEFAULT,
            )
        )
        batch_op.add_column(
            sa.Column(
                "quality_score",
                sa.Float(),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "content_type",
                sa.String(64),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_place_images_visibility_status",
            ["visibility_status"],
        )
        batch_op.create_index(
            "ix_place_images_place_visibility",
            ["place_id", "visibility_status"],
        )


def downgrade() -> None:
    with op.batch_alter_table("place_images") as batch_op:
        batch_op.drop_index("ix_place_images_place_visibility")
        batch_op.drop_index("ix_place_images_visibility_status")
        batch_op.drop_column("content_type")
        batch_op.drop_column("quality_score")
        batch_op.drop_column("visibility_status")
