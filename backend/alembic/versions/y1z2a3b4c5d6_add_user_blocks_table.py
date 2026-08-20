"""add user_blocks table

Revision ID: y1z2a3b4c5d6
Revises: x1y2z3a4b5c6
Create Date: 2026-08-14

Backs app/db/models/user_block.py. Required for App Store review compliance
(Guideline 1.2, User-Generated Content): apps with UGC need a mechanism to
block abusive users, not just report individual content items (the existing
ReportPhoto flow covers the latter).
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "y1z2a3b4c5d6"
down_revision = "x1y2z3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_blocks" in inspector.get_table_names():
        return

    op.create_table(
        "user_blocks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("blocker_id", sa.String(length=128), nullable=False),
        sa.Column("blocked_id", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "blocker_id != blocked_id", name=op.f("ck_user_blocks_no_self_block")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_user_blocks")),
        sa.UniqueConstraint("blocker_id", "blocked_id", name="uq_user_blocks_pair"),
    )
    with op.batch_alter_table("user_blocks", schema=None) as batch_op:
        batch_op.create_index("ix_user_blocks_blocker", ["blocker_id"], unique=False)
        batch_op.create_index("ix_user_blocks_blocked", ["blocked_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "user_blocks" not in inspector.get_table_names():
        return

    with op.batch_alter_table("user_blocks", schema=None) as batch_op:
        batch_op.drop_index("ix_user_blocks_blocked")
        batch_op.drop_index("ix_user_blocks_blocker")
    op.drop_table("user_blocks")
