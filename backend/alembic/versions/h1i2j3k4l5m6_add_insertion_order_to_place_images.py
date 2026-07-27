"""add insertion_order to place_images for PostgreSQL migration

rowid is SQLite-only. PostgreSQL has no rowid and ctid is not stable.
insertion_order is a BigInteger that encodes Google's quality rank
(insertion position per place). It is:
  - assigned at ingest time for new images (post-migration)
  - backfilled from rowid for existing SQLite images during migration

Revision ID: h1i2j3k4l5m6
Revises: g2h3i4j5k6l7
Create Date: 2026-05-08
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "h1i2j3k4l5m6"
down_revision = "g2h3i4j5k6l7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()
    dialect = conn.dialect.name  # "sqlite" or "postgresql"

    with op.batch_alter_table("place_images") as batch_op:
        batch_op.add_column(
            sa.Column(
                "insertion_order",
                sa.BigInteger(),
                nullable=True,
            )
        )
        batch_op.create_index(
            "ix_place_images_place_order",
            ["place_id", "insertion_order"],
        )

    # Backfill insertion_order from rowid (SQLite only).
    # In PostgreSQL this will be done at migration time via a separate
    # backfill script that uses ROW_NUMBER() OVER (PARTITION BY place_id ORDER BY rowid).
    if dialect == "sqlite":
        conn.execute(sa.text("""
            UPDATE place_images
            SET insertion_order = rowid
        """))


def downgrade() -> None:
    with op.batch_alter_table("place_images") as batch_op:
        batch_op.drop_index("ix_place_images_place_order")
        batch_op.drop_column("insertion_order")
