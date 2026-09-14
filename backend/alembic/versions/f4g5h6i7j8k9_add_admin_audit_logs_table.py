"""add admin_audit_logs table

Revision ID: f4g5h6i7j8k9
Revises: e3f4g5h6i7j8
Create Date: 2026-09-14

Backs app/db/models/admin_audit_log.py. A minimal, append-only record of
which admin took which moderation action on which report/submission and
when -- app/api/v1/routes/moderation.py (and menu_submissions.py's review
endpoint) already gate *who* can act via the ADMIN_USER_IDS allowlist, but
had no persistent, queryable log of *what* they did until now.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "f4g5h6i7j8k9"
down_revision = "e3f4g5h6i7j8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "admin_audit_logs" in inspector.get_table_names():
        return

    op.create_table(
        "admin_audit_logs",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("admin_user_id", sa.String(length=128), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("target_type", sa.String(length=32), nullable=False),
        sa.Column("target_id", sa.String(length=36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_admin_audit_logs")),
    )
    with op.batch_alter_table("admin_audit_logs", schema=None) as batch_op:
        batch_op.create_index(
            "ix_admin_audit_logs_admin_user_id", ["admin_user_id"], unique=False
        )
        batch_op.create_index(
            "ix_admin_audit_logs_target", ["target_type", "target_id"], unique=False
        )
        batch_op.create_index(
            "ix_admin_audit_logs_created_at", ["created_at"], unique=False
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "admin_audit_logs" not in inspector.get_table_names():
        return

    with op.batch_alter_table("admin_audit_logs", schema=None) as batch_op:
        batch_op.drop_index("ix_admin_audit_logs_created_at")
        batch_op.drop_index("ix_admin_audit_logs_target")
        batch_op.drop_index("ix_admin_audit_logs_admin_user_id")
    op.drop_table("admin_audit_logs")
