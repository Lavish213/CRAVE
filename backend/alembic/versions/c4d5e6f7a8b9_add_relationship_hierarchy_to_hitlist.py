"""add relationship hierarchy fields to hitlist_saves

Revision ID: c4d5e6f7a8b9
Revises: b3f09f202a2f
Create Date: 2026-09-08

Backs app/db/models/hitlist_save.py's Wave 7 additions (Place Detail
relationship hierarchy, docs/CLAUDE_EXECUTION_BRIEF_WAVES_7_10_2026-09-08.md):
- reason_role/reason_source: why this place was saved, set once at
  save-creation time, never overwritten.
- visit_confirmation_count: a real repeat-visit signal, incremented only
  on the visited False->True transition.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "c4d5e6f7a8b9"
down_revision = "b3f09f202a2f"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("hitlist_saves")}

    if "reason_role" not in existing_columns:
        op.add_column(
            "hitlist_saves",
            sa.Column("reason_role", sa.String(length=32), nullable=True),
        )
    if "reason_source" not in existing_columns:
        op.add_column(
            "hitlist_saves",
            sa.Column("reason_source", sa.String(length=32), nullable=True),
        )
    if "visit_confirmation_count" not in existing_columns:
        op.add_column(
            "hitlist_saves",
            sa.Column(
                "visit_confirmation_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            ),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_columns = {c["name"] for c in inspector.get_columns("hitlist_saves")}

    if "visit_confirmation_count" in existing_columns:
        op.drop_column("hitlist_saves", "visit_confirmation_count")
    if "reason_source" in existing_columns:
        op.drop_column("hitlist_saves", "reason_source")
    if "reason_role" in existing_columns:
        op.drop_column("hitlist_saves", "reason_role")
