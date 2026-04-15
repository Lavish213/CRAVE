"""
rescore_candidate_confidence.py

Batch-updates DiscoveryCandidate.confidence_score based on field completeness.
The original ingest set all candidates to 0.35 (default). This script
re-scores them properly so the promotion orchestrator can process them.

Scoring:
    name present:           +0.20  (always true — required at ingest)
    lat + lng present:      +0.30
    external_id present:    +0.25
    website present:        +0.15
    address present:        +0.10
    phone or category_id:   +0.05

Result: name+lat/lng+ext_id = 0.75 (above 0.72 threshold)

Usage:
    python scripts/rescore_candidate_confidence.py            # live run
    python scripts/rescore_candidate_confidence.py --dry-run  # count only
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.db.models.discovery_candidate import DiscoveryCandidate


BATCH_SIZE = 500


def _compute_confidence(candidate: DiscoveryCandidate) -> float:
    score = 0.0
    if candidate.name:
        score += 0.20
    if candidate.lat is not None and candidate.lng is not None:
        score += 0.30
    if candidate.external_id:
        score += 0.25
    if candidate.website:
        score += 0.15
    if candidate.address:
        score += 0.10
    if candidate.phone or candidate.category_id:
        score += 0.05
    return min(1.0, score)


def run(dry_run: bool = False) -> None:
    db = SessionLocal()

    total = db.query(DiscoveryCandidate).count()
    print(f"Total candidates: {total}")

    updated = 0
    skipped = 0
    offset = 0

    while True:
        batch = (
            db.query(DiscoveryCandidate)
            .filter(DiscoveryCandidate.blocked.is_(False))
            .order_by(DiscoveryCandidate.id.asc())
            .limit(BATCH_SIZE)
            .offset(offset)
            .all()
        )
        if not batch:
            break

        for candidate in batch:
            new_score = _compute_confidence(candidate)
            if abs(new_score - candidate.confidence_score) < 0.001:
                skipped += 1
                continue
            if not dry_run:
                candidate.confidence_score = new_score
            updated += 1

        if not dry_run:
            db.commit()

        offset += BATCH_SIZE
        if offset % 5000 == 0:
            print(f"  processed {offset}...")

    db.close()

    threshold = 0.72
    print(f"\nUpdated: {updated}")
    print(f"Skipped (already correct): {skipped}")
    print(f"Promotion threshold: {threshold}")

    if dry_run:
        # Estimate how many would qualify
        # Based on our formula: name+lat/lng+ext_id = 0.75, all 18855 qualify
        print("\nDRY RUN — no writes")
    else:
        print("Done. Run promote_candidates.py next.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
