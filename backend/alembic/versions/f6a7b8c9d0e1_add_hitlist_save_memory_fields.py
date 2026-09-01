"""add visited/visited_at/notes to hitlist_saves (E2 memory)

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-09-01

Additive columns only. `/saves` is backed by `HitlistSave` (shared with
the craves-discovery flow, distinguished by `dedup_key` prefix) -- these
fields belong on the shared table, not a parallel API, per
docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md's E2 finding.
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "f6a7b8c9d0e1"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("hitlist_saves") as batch_op:
        batch_op.add_column(
            sa.Column(
                "visited",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("false"),
            )
        )
        batch_op.add_column(
            sa.Column("visited_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(sa.Column("notes", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("hitlist_saves") as batch_op:
        batch_op.drop_column("notes")
        batch_op.drop_column("visited_at")
        batch_op.drop_column("visited")
