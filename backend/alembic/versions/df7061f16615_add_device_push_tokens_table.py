"""add device_push_tokens table

Revision ID: df7061f16615
Revises: 982f61551581
Create Date: 2026-08-24

Backs app/db/models/device_push_token.py -- Expo push token registration
for video approve/reject notifications (see
app/services/notifications/expo_push.py and video_processing_worker.py).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "df7061f16615"
down_revision = "982f61551581"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if "device_push_tokens" not in existing_tables:
        op.create_table(
            "device_push_tokens",
            sa.Column("push_token", sa.String(length=255), nullable=False),
            sa.Column("user_id", sa.String(length=128), nullable=False),
            sa.Column("platform", sa.String(length=16), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("push_token", name=op.f("pk_device_push_tokens")),
        )
        op.create_index(
            "ix_device_push_tokens_user_id", "device_push_tokens", ["user_id"]
        )


def downgrade() -> None:
    op.drop_table("device_push_tokens")
