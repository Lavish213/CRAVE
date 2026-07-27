#!/usr/bin/env python3
"""
run_phase3_image_backfill.py
============================
Phase 3 image classification + visibility backfill.

Classifies all place_images where content_type IS NULL:
  - assigns content_type   (plated_food / food_closeup / restaurant_interior /
                            menu_text / exterior / unknown)
  - assigns quality_score  (0.0 – 1.0, position-aware)
  - assigns visibility_status based on quality + content_type rules
  - runs invariant repair per affected place (promotes best image to primary)
  - invalidates all image-related caches at the end

Key design decision
-------------------
All 72k images in this dataset are opaque Google Places photo URLs
(https://places.googleapis.com/v1/places/.../photos/...).
URL keyword classification returns "unknown" for these.
Differentiation comes from POSITION within each place's image set:
  - Google returns photos in quality/relevance order
  - position 0 = their best photo (typically food), score ~0.72 → candidate_primary
  - position 1 = good, score ~0.56 → gallery_only
  - position 2+ = supporting images, score ~0.47 and below → gallery_only

Guarantees
----------
- Idempotent: skips images where content_type IS NOT NULL
- Processes all images in memory per-place for accurate position assignment
- Commits per batch of places (not images)
- No external API calls

Usage
-----
    cd /Users/angelowashington/CRAVE/backend
    python scripts/run_phase3_image_backfill.py --dry-run
    python scripts/run_phase3_image_backfill.py
    python scripts/run_phase3_image_backfill.py --limit 1000
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
for d in (str(BACKEND_DIR), str(ROOT_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("phase3_backfill")

from sqlalchemy import func, select

from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_CANDIDATE_PRIMARY,
    VISIBILITY_GALLERY_ONLY,
    VISIBILITY_HIDDEN,
    VISIBILITY_SHOWCASE,
)
from app.db.session import SessionLocal
from app.services.cache.cache_helpers import invalidate_all_image_caches, invalidate_place
from app.services.images.image_classifier import ImageClassifier
from app.services.images.place_image_invariant_service import PlaceImageInvariantService
from app.services.images.visibility_assigner import VisibilityAssigner

# Process N places per batch commit
PLACE_BATCH_SIZE = 200

UTC = timezone.utc


def _utcnow() -> str:
    return datetime.now(UTC).strftime("%H:%M:%S")


def _print(msg: str) -> None:
    print(f"[{_utcnow()}] {msg}", flush=True)


# ------------------------------------------------------------------
# Core backfill logic
# ------------------------------------------------------------------

def run_backfill(
    *,
    dry_run: bool = False,
    limit_images: Optional[int] = None,
) -> None:
    classifier = ImageClassifier()
    assigner = VisibilityAssigner()
    invariant_svc = PlaceImageInvariantService()

    db = SessionLocal()

    try:
        # ── Baseline counts ───────────────────────────────────────────────
        total_images = db.execute(select(func.count(PlaceImage.id))).scalar_one()
        null_ct = db.execute(
            select(func.count(PlaceImage.id)).where(PlaceImage.content_type.is_(None))
        ).scalar_one()
        null_qs = db.execute(
            select(func.count(PlaceImage.id)).where(PlaceImage.quality_score.is_(None))
        ).scalar_one()

        _print(f"Total images:          {total_images:,}")
        _print(f"content_type NULL:     {null_ct:,}")
        _print(f"quality_score NULL:    {null_qs:,}")

        if dry_run:
            _print("DRY RUN — no writes.")
            _simulate_distribution(classifier, assigner, db, limit_images)
            return

        if null_ct == 0:
            _print("All images already classified. Nothing to do.")
            _run_verification(db)
            return

        # ── Load all unclassified images ordered by place + insertion_order ─
        # IMPORTANT: created_at is identical for all images per place
        # (bulk-inserted in a single transaction). UUIDs are random.
        # insertion_order encodes Google's photo quality ranking (first = best).
        # It is backfilled from SQLite rowid during migration — see alembic
        # revision h1i2j3k4l5m6. Falls back to rowid on un-migrated SQLite DBs.
        _print("Loading images...")
        from sqlalchemy import text as sa_text
        from app.db.models.place_image import PlaceImage as _PI
        _has_insertion_order = hasattr(_PI, "insertion_order")
        _order_col = (
            PlaceImage.insertion_order.asc()
            if _has_insertion_order
            else sa_text("rowid ASC")
        )
        query = (
            select(PlaceImage)
            .where(PlaceImage.content_type.is_(None))
            .order_by(
                PlaceImage.place_id.asc(),
                _order_col,
            )
        )
        if limit_images:
            query = query.limit(limit_images)

        images = list(db.execute(query).scalars().all())
        _print(f"Loaded {len(images):,} images.")

        # ── Group by place to assign position ────────────────────────────
        place_groups: dict[str, list[PlaceImage]] = defaultdict(list)
        for img in images:
            place_groups[img.place_id].append(img)

        _print(f"Unique places: {len(place_groups):,}")

        # ── Process in place batches ──────────────────────────────────────
        dist = {
            VISIBILITY_HIDDEN: 0,
            VISIBILITY_GALLERY_ONLY: 0,
            VISIBILITY_CANDIDATE_PRIMARY: 0,
            VISIBILITY_SHOWCASE: 0,
        }
        total_classified = 0
        affected_place_ids: list[str] = []
        repair_errors = 0
        start = time.time()

        place_ids = list(place_groups.keys())
        batch_num = 0

        for batch_start in range(0, len(place_ids), PLACE_BATCH_SIZE):
            batch_place_ids = place_ids[batch_start: batch_start + PLACE_BATCH_SIZE]
            batch_num += 1

            try:
                for place_id in batch_place_ids:
                    place_images = place_groups[place_id]

                    for position, img in enumerate(place_images):
                        content_type, quality_score = classifier.classify(
                            url=img.url,
                            confidence=float(img.confidence or 0.5),
                            position_in_place=position,
                        )
                        visibility = assigner.assign(
                            quality_score=quality_score,
                            content_type=content_type,
                        )

                        img.content_type = content_type
                        img.quality_score = quality_score
                        img.visibility_status = visibility

                        dist[visibility] = dist.get(visibility, 0) + 1
                        total_classified += 1

                    affected_place_ids.append(place_id)

                db.flush()
                db.commit()

            except Exception as exc:
                db.rollback()
                logger.error("batch_failed batch=%s error=%s", batch_num, exc)
                continue

            elapsed = time.time() - start
            rate = total_classified / elapsed if elapsed > 0 else 0
            _print(
                f"  batch {batch_num}: {total_classified:,} classified"
                f"  ({rate:.0f}/s)"
                f"  showcase={dist[VISIBILITY_SHOWCASE]}"
                f"  candidate={dist[VISIBILITY_CANDIDATE_PRIMARY]}"
                f"  gallery={dist[VISIBILITY_GALLERY_ONLY]}"
                f"  hidden={dist[VISIBILITY_HIDDEN]}"
            )

        # ── Primary re-election: promote best quality_score image ────────
        # Invariant repair fixes violations only. We also need to demote
        # any pre-Phase-3 primary that is no longer the best image.
        # Filter: only non-hidden images are eligible for primary.
        _print(f"\nRe-electing primaries for {len(place_groups):,} places...")
        reelected = 0

        for batch_start in range(0, len(place_ids), PLACE_BATCH_SIZE):
            batch_place_ids = place_ids[batch_start: batch_start + PLACE_BATCH_SIZE]
            try:
                for place_id in batch_place_ids:
                    imgs = place_groups[place_id]
                    eligible = [
                        i for i in imgs
                        if i.visibility_status != VISIBILITY_HIDDEN
                    ]
                    if not eligible:
                        continue

                    best = max(eligible, key=lambda x: x.quality_score or 0.0)
                    current_primary = next((i for i in imgs if i.is_primary), None)

                    if current_primary is None:
                        best.is_primary = True
                        reelected += 1
                    elif current_primary.id != best.id:
                        current_primary.is_primary = False
                        best.is_primary = True
                        reelected += 1

                db.commit()
            except Exception as exc:
                db.rollback()
                logger.error("reelect_batch_failed error=%s", exc)

        _print(f"  Primaries updated: {reelected:,}")

        # ── Invariant repair for all affected places ──────────────────────
        _print(f"Running invariant repair for {len(affected_place_ids):,} places...")

        for i, place_id in enumerate(affected_place_ids):
            try:
                invariant_svc.repair(db=db, place_id=place_id)
                db.commit()
                invalidate_place(place_id)
            except Exception as exc:
                db.rollback()
                repair_errors += 1
                logger.error("repair_failed place_id=%s error=%s", place_id, exc)

            if (i + 1) % 1000 == 0:
                _print(f"  repaired {i + 1:,}/{len(affected_place_ids):,}...")

        # ── Flush image caches ────────────────────────────────────────────
        _print("Invalidating feed/map/search caches...")
        invalidate_all_image_caches()

        # ── Report + verification ─────────────────────────────────────────
        elapsed_total = time.time() - start
        _print("")
        _print("═" * 65)
        _print("PHASE 3 BACKFILL COMPLETE")
        _print("═" * 65)
        _print(f"Classified:        {total_classified:,}")
        _print(f"showcase:          {dist[VISIBILITY_SHOWCASE]:,}")
        _print(f"candidate_primary: {dist[VISIBILITY_CANDIDATE_PRIMARY]:,}")
        _print(f"gallery_only:      {dist[VISIBILITY_GALLERY_ONLY]:,}")
        _print(f"hidden:            {dist[VISIBILITY_HIDDEN]:,}")
        _print(f"Places repaired:   {len(affected_place_ids):,}")
        _print(f"Repair errors:     {repair_errors}")
        _print(f"Time:              {elapsed_total:.1f}s")
        _print("═" * 65)

        _run_verification(db)

    finally:
        db.close()


# ------------------------------------------------------------------
# Verification
# ------------------------------------------------------------------

def _run_verification(db) -> None:
    _print("\nDB VERIFICATION:")

    null_ct = db.execute(
        select(func.count(PlaceImage.id)).where(PlaceImage.content_type.is_(None))
    ).scalar_one()
    _print(f"  content_type IS NULL:    {null_ct:>8,}  (target: ~0)")

    null_qs = db.execute(
        select(func.count(PlaceImage.id)).where(PlaceImage.quality_score.is_(None))
    ).scalar_one()
    _print(f"  quality_score IS NULL:   {null_qs:>8,}  (target: ~0)")

    hidden_primary = db.execute(
        select(func.count(PlaceImage.id)).where(
            PlaceImage.is_primary.is_(True),
            PlaceImage.visibility_status == VISIBILITY_HIDDEN,
        )
    ).scalar_one()
    status = "PASS" if hidden_primary == 0 else "FAIL"
    _print(f"  hidden primaries:        {hidden_primary:>8,}  [{status}]")

    score_stats = db.execute(
        select(
            func.min(PlaceImage.quality_score),
            func.max(PlaceImage.quality_score),
            func.avg(PlaceImage.quality_score),
        )
    ).one()
    if score_stats[0] is not None:
        _print(
            f"  quality_score:           "
            f"min={score_stats[0]:.4f}  "
            f"max={score_stats[1]:.4f}  "
            f"avg={score_stats[2]:.4f}"
        )

    _print("  Visibility distribution:")
    vis_rows = db.execute(
        select(PlaceImage.visibility_status, func.count(PlaceImage.id))
        .group_by(PlaceImage.visibility_status)
        .order_by(func.count(PlaceImage.id).desc())
    ).all()
    total = sum(r[1] for r in vis_rows)
    for status_val, count in vis_rows:
        pct = count / total * 100 if total else 0
        _print(f"    {status_val:<24} {count:>8,}  ({pct:.1f}%)")


# ------------------------------------------------------------------
# Dry-run simulation
# ------------------------------------------------------------------

def _simulate_distribution(classifier, assigner, db, limit_images) -> None:
    _print("\nSimulating classification (no writes)...")

    from sqlalchemy import text as sa_text
    from app.db.models.place_image import PlaceImage as _PI2
    _has_insertion_order_sim = hasattr(_PI2, "insertion_order")
    _order_col_sim = (
        PlaceImage.insertion_order.asc()
        if _has_insertion_order_sim
        else sa_text("rowid ASC")
    )
    query = (
        select(PlaceImage)
        .where(PlaceImage.content_type.is_(None))
        .order_by(
            PlaceImage.place_id.asc(),
            _order_col_sim,
        )
    )
    if limit_images:
        query = query.limit(limit_images)

    images = list(db.execute(query).scalars().all())

    place_groups: dict[str, list[PlaceImage]] = defaultdict(list)
    for img in images:
        place_groups[img.place_id].append(img)

    dist: dict[str, int] = defaultdict(int)
    ct_dist: dict[str, int] = defaultdict(int)

    for place_id, place_images in place_groups.items():
        for position, img in enumerate(place_images):
            ct, qs = classifier.classify(
                url=img.url,
                confidence=float(img.confidence or 0.5),
                position_in_place=position,
            )
            vis = assigner.assign(quality_score=qs, content_type=ct)
            dist[vis] += 1
            ct_dist[ct] += 1

    total = sum(dist.values())
    _print(f"\nSimulated distribution over {total:,} images:")
    for vis, count in sorted(dist.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total else 0
        _print(f"  {vis:<24} {count:>8,}  ({pct:.1f}%)")

    _print("\nContent types:")
    for ct, count in sorted(ct_dist.items(), key=lambda x: -x[1]):
        pct = count / total * 100 if total else 0
        _print(f"  {ct:<24} {count:>8,}  ({pct:.1f}%)")

    # Score sample
    sample_place_id = next(iter(place_groups))
    sample_images = place_groups[sample_place_id]
    _print(f"\nSample place ({sample_place_id}) — {len(sample_images)} images:")
    for position, img in enumerate(sample_images):
        ct, qs = classifier.classify(
            url=img.url,
            confidence=float(img.confidence or 0.5),
            position_in_place=position,
        )
        vis = assigner.assign(quality_score=qs, content_type=ct)
        _print(f"  pos={position}  score={qs:.4f}  {ct:<10}  {vis}")


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Phase 3 image classification backfill")
    parser.add_argument("--dry-run", action="store_true", help="Simulate, no writes")
    parser.add_argument("--limit", type=int, default=None, help="Max images to process")
    args = parser.parse_args()

    run_backfill(dry_run=args.dry_run, limit_images=args.limit)


if __name__ == "__main__":
    main()
