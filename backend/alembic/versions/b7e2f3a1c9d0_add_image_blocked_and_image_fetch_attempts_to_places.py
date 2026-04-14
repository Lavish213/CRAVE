"""add image_blocked and image_fetch_attempts to places

Revision ID: b7e2f3a1c9d0
Revises: a3f1b2c4d5e6
Create Date: 2026-04-14

"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = 'b7e2f3a1c9d0'
down_revision = 'e0c588405366'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("places") as batch_op:
        batch_op.add_column(
            sa.Column(
                "image_fetch_attempts",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "image_blocked",
                sa.Boolean(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.create_index("ix_places_image_blocked", ["image_blocked"])


def downgrade() -> None:
    with op.batch_alter_table("places") as batch_op:
        batch_op.drop_index("ix_places_image_blocked")
        batch_op.drop_column("image_blocked")
        batch_op.drop_column("image_fetch_attempts")
