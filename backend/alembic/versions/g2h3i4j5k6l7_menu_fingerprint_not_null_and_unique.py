"""menu_items fingerprint NOT NULL + unique constraint
Replaces old (place_id, name, category) unique with (place_id, fingerprint) unique.
Also drops legacy price Float column.

Revision ID: g2h3i4j5k6l7
Revises: g1h2i3j4k5l6
Create Date: 2026-05-07

PREREQUISITE:
    Run scripts/backfill_menu_fingerprints.py and confirm 0 NULL fingerprints
    before applying this migration.

    Verify with:
        SELECT COUNT(*) FROM menu_items WHERE fingerprint IS NULL;
        -- Must return 0

DANGER:
    This migration drops the 'price' column permanently.
    price_cents was backfilled in g1h2i3j4k5l6.
    Confirm price_cents data is correct before applying.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "g2h3i4j5k6l7"
down_revision = "g1h2i3j4k5l6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Safety check — abort if any NULL fingerprints remain
    conn = op.get_bind()
    result = conn.execute(
        sa.text("SELECT COUNT(*) FROM menu_items WHERE fingerprint IS NULL")
    )
    null_count = result.scalar()
    if null_count and null_count > 0:
        raise RuntimeError(
            f"Cannot apply migration: {null_count} menu_items rows have NULL fingerprint. "
            "Run scripts/backfill_menu_fingerprints.py first."
        )

    with op.batch_alter_table("menu_items") as batch_op:
        # Make fingerprint NOT NULL
        batch_op.alter_column("fingerprint", nullable=False)

        # Drop old name+category unique constraint
        batch_op.drop_constraint("uq_menu_place_name_category", type_="unique")

        # Add new fingerprint unique constraint
        batch_op.create_unique_constraint(
            "uq_menu_place_fingerprint",
            ["place_id", "fingerprint"],
        )

        # Add fingerprint index
        batch_op.create_index("ix_menu_fingerprint", ["fingerprint"])

        # Drop legacy price Float column (data preserved in price_cents)
        # Drop both custom index and the auto-named index SQLAlchemy created
        batch_op.drop_index("ix_menu_price")
        try:
            batch_op.drop_index("ix_menu_items_menu_items_price")
        except Exception:
            pass  # may not exist in all environments
        batch_op.drop_column("price")


def downgrade() -> None:
    with op.batch_alter_table("menu_items") as batch_op:
        # Restore price Float column (values lost — only price_cents survives)
        batch_op.add_column(
            sa.Column("price", sa.Float(), nullable=True)
        )
        batch_op.create_index("ix_menu_price", ["price"])

        # Restore old unique constraint
        batch_op.drop_constraint("uq_menu_place_fingerprint", type_="unique")
        batch_op.drop_index("ix_menu_fingerprint")
        batch_op.create_unique_constraint(
            "uq_menu_place_name_category",
            ["place_id", "name", "category"],
        )

        # Make fingerprint nullable again
        batch_op.alter_column("fingerprint", nullable=True)
