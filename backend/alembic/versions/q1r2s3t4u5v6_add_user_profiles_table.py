"""add user_profiles table

App-specific profile data for a Supabase-authenticated user (username,
display name, avatar, bio) — Supabase itself has none of this, and every
other table just stores a bare user_id string with nothing to show for it.

Revision ID: q1r2s3t4u5v6
Revises: p1q2r3s4t5u6
Create Date: 2026-08-02
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "q1r2s3t4u5v6"
down_revision = "p1q2r3s4t5u6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(length=128), nullable=False),
        sa.Column("username", sa.String(length=30), nullable=False),
        sa.Column("display_name", sa.String(length=60), nullable=True),
        sa.Column("avatar_url", sa.String(length=1024), nullable=True),
        sa.Column("bio", sa.String(length=280), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_profiles")),
    )
    with op.batch_alter_table("user_profiles", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_user_profiles_username"), ["username"], unique=True
        )


def downgrade() -> None:
    with op.batch_alter_table("user_profiles", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_profiles_username"))
    op.drop_table("user_profiles")
