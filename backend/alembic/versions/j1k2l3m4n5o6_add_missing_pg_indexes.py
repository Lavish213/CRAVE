"""add missing pg indexes

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-05-08 00:00:00.000000

"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "j1k2l3m4n5o6"
down_revision = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Compound index for the "get active sources for a place" query pattern:
    #   SELECT * FROM menu_sources WHERE place_id = :pid AND is_active = TRUE
    # Separate indexes on place_id and is_active already exist; this compound
    # index allows PostgreSQL to satisfy both predicates from a single index scan.
    op.create_index(
        "ix_menu_source_place_active",
        "menu_sources",
        ["place_id", "is_active"],
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_menu_source_place_active",
        table_name="menu_sources",
    )
