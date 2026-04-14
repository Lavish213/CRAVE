#!/usr/bin/env python3
"""
Dedup audit script.

Usage:
    python scripts/run_dedup_audit.py [--dry-run] [--city-id CITY_ID] [--merge]

Flags:
    --dry-run    Print findings without writing (default: True)
    --merge      Actually execute auto-merge for high-confidence pairs
    --city-id    Only scan a specific city (default: all active cities)
"""
from __future__ import annotations

import argparse
import logging
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.db.models.city import City
from app.services.dedup.place_deduplicator import find_duplicates_in_city
from app.services.dedup.dedup_merger import merge_duplicate_places


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


def run(*, city_id: str | None, dry_run: bool, merge: bool) -> None:
    db = SessionLocal()
    try:
        # Gather cities to scan
        if city_id:
            city_ids = [city_id]
        else:
            cities = db.execute(select(City)).scalars().all()
            city_ids = [c.id for c in cities]

        total_pairs = 0
        total_merged = 0

        for cid in city_ids:
            report = find_duplicates_in_city(db, cid)

            print(
                f"\n[city={cid}] checked={report.total_checked} "
                f"pairs={report.pairs_found} "
                f"auto_merge={report.auto_merge_pairs} "
                f"review={report.review_pairs}"
            )

            for pair in report.pairs:
                flag = "AUTO_MERGE" if pair.auto_merge else "REVIEW"
                print(
                    f"  [{flag}] score={pair.score:.3f} "
                    f"'{pair.name_a}' ({pair.place_a_id[:8]}) "
                    f"<-> "
                    f"'{pair.name_b}' ({pair.place_b_id[:8]})"
                )

                if merge and pair.auto_merge and not dry_run:
                    winner_id = merge_duplicate_places(
                        db,
                        place_a_id=pair.place_a_id,
                        place_b_id=pair.place_b_id,
                        dry_run=False,
                    )
                    if winner_id:
                        db.commit()
                        total_merged += 1
                        print(f"    => merged: winner={winner_id}")

            total_pairs += report.pairs_found

        print(
            f"\n=== DEDUP AUDIT COMPLETE ===\n"
            f"  cities scanned : {len(city_ids)}\n"
            f"  total pairs    : {total_pairs}\n"
            f"  merged         : {total_merged}\n"
            f"  dry_run        : {dry_run}\n"
        )

    except Exception:
        logger.exception("dedup_audit_failed")
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="CRAVE place dedup audit")
    parser.add_argument("--city-id", default=None)
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument("--merge", action="store_true", default=False)
    args = parser.parse_args()

    dry_run = args.dry_run and not args.merge
    run(city_id=args.city_id, dry_run=dry_run, merge=args.merge)


if __name__ == "__main__":
    main()
