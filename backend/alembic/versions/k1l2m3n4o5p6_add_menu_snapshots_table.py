"""add menu_snapshots table

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2026-07-26

The `MenuSnapshot` model (app/db/models/menu_snapshot.py) has existed in code
with no corresponding migration — every write via `MenuSnapshotWriter.write()`
(app/pipeline/snapshot_writer.py, called from
app/services/menu/menu_extraction_router.py) was failing against a missing
table, silently caught and logged. This migration creates the table to match
the model exactly, including its five indexes.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "k1l2m3n4o5p6"
down_revision = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "menu_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "place_id",
            sa.String(36),
            sa.ForeignKey("places.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("extraction_method", sa.String(64), nullable=False),
        sa.Column("source_url", sa.String(1024), nullable=True),
        sa.Column(
            "success",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("1"),
        ),
        sa.Column(
            "item_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("raw_payload", sa.JSON(), nullable=True),
        sa.Column("normalized_items", sa.JSON(), nullable=True),
        sa.Column("error_message", sa.String(500), nullable=True),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("extractor_count", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_index(
        "ix_menu_snapshots_place_id",
        "menu_snapshots",
        ["place_id"],
    )
    op.create_index(
        "ix_menu_snapshots_place_created",
        "menu_snapshots",
        ["place_id", "created_at"],
    )
    op.create_index(
        "ix_menu_snapshots_method",
        "menu_snapshots",
        ["extraction_method"],
    )
    op.create_index(
        "ix_menu_snapshots_success",
        "menu_snapshots",
        ["success"],
    )
    op.create_index(
        "ix_menu_snapshots_lookup",
        "menu_snapshots",
        ["place_id", "created_at"],
    )
    op.create_index(
        "ix_menu_snapshots_source_url",
        "menu_snapshots",
        ["source_url"],
    )
    op.create_index(
        "ix_menu_snapshots_created_at",
        "menu_snapshots",
        ["created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_menu_snapshots_created_at", table_name="menu_snapshots")
    op.drop_index("ix_menu_snapshots_source_url", table_name="menu_snapshots")
    op.drop_index("ix_menu_snapshots_lookup", table_name="menu_snapshots")
    op.drop_index("ix_menu_snapshots_success", table_name="menu_snapshots")
    op.drop_index("ix_menu_snapshots_method", table_name="menu_snapshots")
    op.drop_index("ix_menu_snapshots_place_created", table_name="menu_snapshots")
    op.drop_index("ix_menu_snapshots_place_id", table_name="menu_snapshots")
    op.drop_table("menu_snapshots")
