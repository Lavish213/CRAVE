from __future__ import annotations

import sys
import time
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.services.scoring.recompute import recompute_place_scores


# =========================================================
# CONFIG (LOCKED)
# =========================================================

DEFAULT_BATCH_SIZE = 250


# =========================================================
# CLI ENTRY
# =========================================================

def main() -> None:
    """
    Production-locked CLI job to recompute place scores.

    Usage:

        PYTHONPATH=backend python backend/app/jobs/recompute_scores.py
        PYTHONPATH=backend python backend/app/jobs/recompute_scores.py <city_id>
        PYTHONPATH=backend python backend/app/jobs/recompute_scores.py <city_id> <limit>
        PYTHONPATH=backend python backend/app/jobs/recompute_scores.py <city_id> <limit> --dry-run
        PYTHONPATH=backend python backend/app/jobs/recompute_scores.py --include-inactive

    Behavior:

        - Deterministic ordering
        - Batched commits
        - Atomic per batch
        - Optional city filtering
        - Optional limit
        - Optional dry-run
        - Optional inactive inclusion
        - Safe rollback on failure
        - Scheduler-safe
        - Prevents N+1 by eager-loading categories
    """

    city_id: Optional[str] = None
    limit: Optional[int] = None
    dry_run: bool = False
    include_inactive: bool = False

    # -------------------------------------------------
    # Parse Args
    # -------------------------------------------------

    args = sys.argv[1:]

    for arg in args:
        if arg == "--dry-run":
            dry_run = True
        elif arg == "--include-inactive":
            include_inactive = True

    positional = [a for a in args if not a.startswith("--")]

    if len(positional) >= 1:
        city_id = positional[0]

    if len(positional) >= 2:
        try:
            limit = int(positional[1])
            if limit <= 0:
                raise ValueError
        except ValueError:
            print("❌ Limit must be a positive integer.")
            sys.exit(1)

    start_time = time.perf_counter()

    db: Session = SessionLocal()

    try:
        total_processed = 0
        total_updated = 0

        # -------------------------------------------------
        # Deterministic Query (with eager loading)
        # -------------------------------------------------
        # IMPORTANT:
        # - selectinload prevents N+1 queries on place.categories
        # - ordering by Place.id keeps processing stable across runs
        # -------------------------------------------------

        stmt = (
            select(Place)
            .options(selectinload(Place.categories))
            .order_by(Place.id.asc())
        )

        if not include_inactive:
            stmt = stmt.where(Place.is_active.is_(True))

        if city_id:
            stmt = stmt.where(Place.city_id == city_id)

        if limit:
            stmt = stmt.limit(limit)

        result = db.execute(stmt).scalars()

        batch: list[Place] = []

        for place in result:
            batch.append(place)
            total_processed += 1

            if len(batch) >= DEFAULT_BATCH_SIZE:
                total_updated += _process_batch(db, batch, dry_run=dry_run)
                batch.clear()

        # Final remainder
        if batch:
            total_updated += _process_batch(db, batch, dry_run=dry_run)

        elapsed = round(time.perf_counter() - start_time, 3)

        print("\n==========================================")
        print("Recompute Job Complete")
        print("------------------------------------------")
        print(f"Processed: {total_processed}")
        print(f"Updated:   {total_updated}")
        print(f"Dry Run:   {dry_run}")
        print(f"Elapsed:   {elapsed}s")
        print("==========================================\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Fatal error during recompute: {e}\n")
        sys.exit(1)

    finally:
        db.close()


# =========================================================
# BATCH PROCESSOR (LOCKED)
# =========================================================

def _process_batch(
    db: Session,
    places: list[Place],
    *,
    dry_run: bool = False,
) -> int:
    """
    Processes one batch atomically.

    Guarantees:
        - Deterministic
        - Rollback on failure
        - No partial writes
        - Dry-run never persists
    """

    try:
        updated = recompute_place_scores(db, places=places)

        if dry_run:
            db.rollback()
            return updated

        db.commit()
        return updated

    except Exception:
        db.rollback()
        raise


# =========================================================
# ENTRYPOINT
# =========================================================

if __name__ == "__main__":
    main()