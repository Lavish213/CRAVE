"""
Backfill fingerprints for existing menu_items rows.

Run AFTER alembic upgrade g1h2i3j4k5l6 (which adds the nullable fingerprint column).
Run BEFORE alembic upgrade g2h3i4j5k6l7 (which makes fingerprint NOT NULL + adds unique constraint).

This script is idempotent: safe to re-run. Only updates rows where fingerprint IS NULL.

Usage:
    cd backend
    python scripts/backfill_menu_fingerprints.py [--dry-run] [--batch-size 500]
"""
from __future__ import annotations

import argparse
import logging
import sys

sys.path.insert(0, ".")

from sqlalchemy import text
from app.db.session import SessionLocal
from app.services.menu.normalization.fingerprint import build_menu_fingerprint

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_fingerprints")

DEFAULT_BATCH_SIZE = 500


def backfill(dry_run: bool = False, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
    db = SessionLocal()
    try:
        total_row = db.execute(
            text("SELECT COUNT(*) FROM menu_items WHERE fingerprint IS NULL")
        ).fetchone()
        total = total_row[0] if total_row else 0

        if total == 0:
            logger.info("No rows need backfill — fingerprint already populated for all rows.")
            return

        logger.info("Rows needing fingerprint: %s", total)
        if dry_run:
            logger.info("DRY RUN — no changes written.")
            return

        updated_total = 0

        while True:
            rows = db.execute(
                text(
                    "SELECT id, name, category FROM menu_items "
                    "WHERE fingerprint IS NULL "
                    "LIMIT :limit"
                ),
                {"limit": batch_size},
            ).fetchall()

            if not rows:
                break

            updates: list[dict] = []

            for row in rows:
                row_id, name, category = row[0], row[1], row[2]

                fp = build_menu_fingerprint(
                    name=name or "",
                    section=category,
                    currency="usd",
                )

                updates.append({"id": row_id, "fingerprint": fp})

            # Bulk update
            for u in updates:
                db.execute(
                    text("UPDATE menu_items SET fingerprint = :fp WHERE id = :id"),
                    {"fp": u["fingerprint"], "id": u["id"]},
                )

            db.commit()
            updated_total += len(updates)

            logger.info(
                "Progress: %s / %s updated (%.1f%%)",
                updated_total,
                total,
                (updated_total / total * 100) if total else 0,
            )

        # Verify
        null_check = db.execute(
            text("SELECT COUNT(*) FROM menu_items WHERE fingerprint IS NULL")
        ).fetchone()
        remaining_nulls = null_check[0] if null_check else -1

        if remaining_nulls == 0:
            logger.info(
                "Backfill complete. %s rows updated. 0 NULL fingerprints remain.",
                updated_total,
            )
            logger.info(
                "READY for: alembic upgrade g2h3i4j5k6l7 (fingerprint NOT NULL + unique constraint)"
            )
        else:
            logger.error(
                "BACKFILL INCOMPLETE: %s NULL fingerprints remain. "
                "Do NOT run g2h3i4j5k6l7 until this is 0.",
                remaining_nulls,
            )
            sys.exit(1)

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill menu_items fingerprints")
    parser.add_argument("--dry-run", action="store_true", help="Count rows, do not update")
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    args = parser.parse_args()
    backfill(dry_run=args.dry_run, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
