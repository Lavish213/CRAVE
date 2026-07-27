"""
Menu Publish Backfill — CRAVE

place_truths has 430+ menus that were extracted but never published
to the menu_items table. This script calls MenuPublisher.publish()
for every place that has a menu truth but no menu_items rows.

Run:
    cd backend
    python scripts/run_menu_publish_backfill.py

Estimated time: ~2-5 min for 430 places.
"""
from __future__ import annotations

import logging
import sys

sys.path.insert(0, ".")

from sqlalchemy import text

from app.db.session import SessionLocal
from app.services.menu.menu_publisher import MenuPublisher


logging.basicConfig(level=logging.WARNING)


def main():
    db = SessionLocal()

    try:
        # All place_ids with menu truths
        rows = db.execute(text("""
            SELECT pt.place_id
            FROM place_truths pt
            LEFT JOIN (
                SELECT place_id, COUNT(*) AS cnt
                FROM menu_items
                GROUP BY place_id
            ) mi ON mi.place_id = pt.place_id
            WHERE pt.truth_type = 'menu'
            AND (mi.cnt IS NULL OR mi.cnt = 0)
            ORDER BY pt.created_at ASC
        """)).fetchall()

        place_ids = [r[0] for r in rows]
        total = len(place_ids)
        print(f"Places needing publish: {total}", flush=True)

        if total == 0:
            print("Nothing to publish — menu_items is already up to date")
            return

        publisher = MenuPublisher()
        succeeded = 0
        failed = 0
        total_written = 0

        for i, place_id in enumerate(place_ids, 1):
            try:
                written = publisher.publish(place_id=place_id, db=db)
                db.commit()
                total_written += written
                succeeded += 1

                if i % 25 == 0 or i == total:
                    print(
                        f"  [{i:>4}/{total}]  succeeded={succeeded}  "
                        f"failed={failed}  items_written={total_written}",
                        flush=True,
                    )

            except Exception as exc:
                failed += 1
                print(f"  FAIL place_id={place_id} error={exc}", flush=True)

        print(f"\n=== DONE ===", flush=True)
        print(f"Places processed: {total}", flush=True)
        print(f"Succeeded:        {succeeded}", flush=True)
        print(f"Failed:           {failed}", flush=True)
        print(f"menu_items rows:  {total_written}", flush=True)

        # Final count
        row = db.execute(text("SELECT COUNT(*) FROM menu_items")).fetchone()
        print(f"menu_items total: {row[0]:,}", flush=True)

    finally:
        db.close()


if __name__ == "__main__":
    main()
