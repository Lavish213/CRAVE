"""truth stabilization schema — menu_items price_cents + fingerprint,
place menu_confidence + extraction tracking, menu_sources lineage fields

Revision ID: g1h2i3j4k5l6
Revises: b7e2f3a1c9d0
Create Date: 2026-05-07

MIGRATION ORDER — DO NOT SKIP STEPS:
1. Add nullable columns
2. Backfill fingerprints (Python script: scripts/backfill_menu_fingerprints.py)
3. Verify zero NULL fingerprints before making NOT NULL
4. Drop old price column + old unique constraint
5. Add new unique constraint on (place_id, fingerprint)

ROLLBACK PLAN:
- price column is preserved as price_legacy until step 4 is confirmed safe
- Run downgrade() to restore price column and old constraint
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "g1h2i3j4k5l6"
down_revision = "b7e2f3a1c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ==================================================================
    # 1. menu_items — add price_cents, fingerprint, confidence, lineage
    # ==================================================================
    with op.batch_alter_table("menu_items") as batch_op:
        # price_cents: canonical integer cents. NULL = unknown price.
        batch_op.add_column(
            sa.Column("price_cents", sa.Integer(), nullable=True)
        )
        # fingerprint: SHA256(name|section|currency). Added nullable first,
        # backfilled by scripts/backfill_menu_fingerprints.py, then made NOT NULL.
        batch_op.add_column(
            sa.Column("fingerprint", sa.String(64), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "confidence_score",
                sa.Float(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("provider", sa.String(32), nullable=True)
        )
        batch_op.add_column(
            sa.Column("source_type", sa.String(32), nullable=True)
        )

        # Add indexes
        batch_op.create_index("ix_menu_price_cents", ["price_cents"])
        batch_op.create_index("ix_menu_provider", ["provider"])

    # Backfill price_cents AFTER batch closes — SQLite batch_alter_table rebuilds
    # the table and the new column only exists once the context manager exits.
    # price was stored as raw cents in float (e.g. 1299.0 = $12.99).
    op.execute(
        sa.text(
            "UPDATE menu_items SET price_cents = CAST(price AS INTEGER)"
            " WHERE price IS NOT NULL AND price_cents IS NULL"
        )
    )

    # NOTE: fingerprint backfill and NOT NULL constraint are applied AFTER
    # running: python scripts/backfill_menu_fingerprints.py
    # That script is safe to re-run (idempotent).
    # The not-null constraint and unique index are added in a separate migration
    # (g2h3i4j5k6l7_menu_fingerprint_not_null.py) after backfill is confirmed.

    # ==================================================================
    # 2. places — add menu truth fields
    # ==================================================================
    with op.batch_alter_table("places") as batch_op:
        batch_op.add_column(
            sa.Column(
                "menu_confidence",
                sa.Float(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column(
                "menu_extraction_attempted_at",
                sa.DateTime(timezone=True),
                nullable=True,
            )
        )
        batch_op.add_column(
            sa.Column(
                "menu_extraction_failure_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )

    # ==================================================================
    # 3. menu_sources — add lineage fields
    # ==================================================================
    with op.batch_alter_table("menu_sources") as batch_op:
        batch_op.add_column(
            sa.Column("provider", sa.String(32), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "confidence",
                sa.Float(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("discovered_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_verified_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("last_success_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "failure_count",
                sa.Integer(),
                nullable=False,
                server_default="0",
            )
        )
        batch_op.add_column(
            sa.Column("invalidated_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("invalidation_reason", sa.String(128), nullable=True)
        )
        batch_op.create_index("ix_menu_source_provider", ["provider"])
        batch_op.create_index("ix_menu_source_confidence", ["confidence"])
        batch_op.create_index("ix_menu_source_last_verified", ["last_verified_at"])


def downgrade() -> None:
    with op.batch_alter_table("menu_sources") as batch_op:
        batch_op.drop_index("ix_menu_source_last_verified")
        batch_op.drop_index("ix_menu_source_confidence")
        batch_op.drop_index("ix_menu_source_provider")
        batch_op.drop_column("invalidation_reason")
        batch_op.drop_column("invalidated_at")
        batch_op.drop_column("failure_count")
        batch_op.drop_column("last_success_at")
        batch_op.drop_column("last_verified_at")
        batch_op.drop_column("discovered_at")
        batch_op.drop_column("confidence")
        batch_op.drop_column("provider")

    with op.batch_alter_table("places") as batch_op:
        batch_op.drop_column("menu_extraction_failure_count")
        batch_op.drop_column("menu_extraction_attempted_at")
        batch_op.drop_column("menu_confidence")

    with op.batch_alter_table("menu_items") as batch_op:
        batch_op.drop_index("ix_menu_provider")
        batch_op.drop_index("ix_menu_price_cents")
        batch_op.drop_column("source_type")
        batch_op.drop_column("provider")
        batch_op.drop_column("confidence_score")
        batch_op.drop_column("fingerprint")
        batch_op.drop_column("price_cents")
