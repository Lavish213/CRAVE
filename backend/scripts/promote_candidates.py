"""
promote_candidates.py

One-time bulk promotion script. Loops promote_ready_candidates_v2 until
all eligible DiscoveryCandidates are promoted (confidence >= 0.72,
status="candidate", resolved=False, blocked=False).

After all promotions complete, writes affected city_ids to the score
recompute queue so place scores are updated before the next feed request.

Usage:
    python scripts/promote_candidates.py            # live run
    python scripts/promote_candidates.py --dry-run  # count eligible only
    python scripts/promote_candidates.py --batch-size 200  # custom batch
"""
from __future__ import annotations

import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pathlib import Path
from typing import Set

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.discovery.promotion_orchestrator_v2 import (
    promote_ready_candidates_v2,
    MIN_CONFIDENCE_THRESHOLD,
)

BASE_DIR = Path(__file__).resolve().parents[1]
QUEUE_FILE = BASE_DIR / "var" / "queue" / "recompute_scores.queue"


def _count_eligible(db: Session) -> int:
    return (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.status == "candidate")
        .filter(DiscoveryCandidate.resolved.is_(False))
        .filter(DiscoveryCandidate.blocked.is_(False))
        .filter(DiscoveryCandidate.confidence_score >= MIN_CONFIDENCE_THRESHOLD)
        .count()
    )


def _collect_affected_cities(db: Session) -> Set[str]:
    """Cities that had candidates promoted (i.e. now have promoted status)."""
    rows = (
        db.query(DiscoveryCandidate.city_id)
        .filter(DiscoveryCandidate.status == "promoted")
        .filter(DiscoveryCandidate.city_id.isnot(None))
        .distinct()
        .all()
    )
    return {r.city_id for r in rows if r.city_id}


def _write_recompute_queue(city_ids: Set[str]) -> None:
    QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
    existing: Set[str] = set()
    if QUEUE_FILE.exists():
        for line in QUEUE_FILE.read_text().splitlines():
            line = line.strip()
            if line:
                existing.add(line)
    merged = existing | city_ids
    QUEUE_FILE.write_text("\n".join(sorted(merged)) + "\n")
    print(f"  Queued {len(merged)} city_ids for score recompute → {QUEUE_FILE}")


def run(dry_run: bool = False, batch_size: int = 200) -> None:
    db = SessionLocal()

    try:
        eligible = _count_eligible(db)
        print(f"Eligible candidates (confidence >= {MIN_CONFIDENCE_THRESHOLD}): {eligible}")

        if dry_run:
            print("DRY RUN — no writes")
            return

        if eligible == 0:
            print("Nothing to promote.")
            return

        total_promoted = 0
        run_num = 0
        t0 = time.monotonic()

        while True:
            remaining = _count_eligible(db)
            if remaining == 0:
                break

            run_num += 1
            promoted = promote_ready_candidates_v2(db=db, limit=batch_size)
            total_promoted += promoted

            elapsed = time.monotonic() - t0
            print(
                f"  batch {run_num}: promoted={promoted}  total={total_promoted}  "
                f"remaining≈{remaining - promoted}  elapsed={elapsed:.1f}s"
            )

            if promoted == 0:
                # No progress — stop to avoid infinite loop
                print("  No progress in last batch — stopping.")
                break

        print(f"\nDone. Total promoted: {total_promoted} in {run_num} batches.")

        if total_promoted > 0:
            city_ids = _collect_affected_cities(db)
            _write_recompute_queue(city_ids)
            print(f"Affected cities: {len(city_ids)}")

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=200)
    args = parser.parse_args()
    run(dry_run=args.dry_run, batch_size=args.batch_size)
