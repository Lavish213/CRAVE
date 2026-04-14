from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.services.scoring.recompute import recompute_place_scores


# ------------------------------------------------------------
# Queue location (must match enqueue file)
# ------------------------------------------------------------

APP_DIR = Path(__file__).resolve().parents[2]
VAR_DIR = APP_DIR / "var"
QUEUE_DIR = VAR_DIR / "queue"
QUEUE_FILE = QUEUE_DIR / "recompute_scores.queue"


def _ensure_queue_dir() -> None:
    """Create the queue directory if it does not exist."""
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Job:
    type: str
    created_at: str
    payload: Dict[str, Any]


def _read_jobs(path: Path) -> Tuple[list[Job], bool]:
    """
    Read all jobs currently queued.
    Returns: (jobs, had_file)

    File is treated as append-only; worker "consumes" by truncating after successful parse.
    """
    _ensure_queue_dir()
    if not path.exists():
        return [], False

    raw = path.read_text(encoding="utf-8").strip()
    if not raw:
        return [], True

    jobs: list[Job] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        data = json.loads(line)
        jobs.append(
            Job(
                type=str(data.get("type")),
                created_at=str(data.get("created_at")),
                payload=dict(data.get("payload") or {}),
            )
        )

    return jobs, True


def _truncate_queue(path: Path) -> None:
    _ensure_queue_dir()
    path.write_text("", encoding="utf-8")


def _clamp_limit(limit: Optional[int]) -> Optional[int]:
    if limit is None:
        return None
    try:
        limit = int(limit)
    except Exception:
        return None
    return max(1, limit)


def _iter_places_for_recompute(
    db: Session,
    *,
    city_id: Optional[str],
    limit: Optional[int],
    batch_size: int,
) -> Iterable[list[Place]]:
    """
    Deterministic batching:
      - WHERE city_id if provided
      - ORDER BY id ASC (stable)
      - batches of batch_size
    """
    limit = _clamp_limit(limit)

    base = select(Place).order_by(Place.id.asc())
    if city_id:
        base = base.where(Place.city_id == city_id)

    fetched = 0
    offset = 0

    while True:
        stmt = base.limit(batch_size).offset(offset)
        rows = db.execute(stmt).scalars().all()

        if not rows:
            break

        # Apply global limit across batches (if requested)
        if limit is not None:
            remaining = limit - fetched
            if remaining <= 0:
                break
            if len(rows) > remaining:
                rows = rows[:remaining]

        yield rows

        fetched += len(rows)
        offset += batch_size

        if limit is not None and fetched >= limit:
            break


def run_recompute_job(
    db: Session,
    *,
    city_id: Optional[str],
    limit: Optional[int],
    batch_size: int = 500,
    commit_every_batch: bool = True,
) -> int:
    """
    Production-safe recompute runner:
      - no randomness
      - deterministic batch ordering
      - commits per batch (keeps transactions small)
    """
    total_updated = 0

    for batch in _iter_places_for_recompute(
        db,
        city_id=city_id,
        limit=limit,
        batch_size=batch_size,
    ):
        updated = recompute_place_scores(db, places=batch)
        total_updated += updated

        if commit_every_batch:
            db.commit()

    return total_updated


def worker_once() -> int:
    """
    Process queued jobs once.
    If queue is empty: returns 0.
    """
    jobs, had_file = _read_jobs(QUEUE_FILE)

    if not jobs:
        return 0

    # Consume queue AFTER successful parsing
    _truncate_queue(QUEUE_FILE)

    updated_total = 0
    db = SessionLocal()
    try:
        for job in jobs:
            if job.type != "recompute_scores":
                continue

            city_id = job.payload.get("city_id")
            limit = job.payload.get("limit")

            updated = run_recompute_job(
                db,
                city_id=city_id,
                limit=limit,
                batch_size=500,
                commit_every_batch=True,
            )
            updated_total += updated

        # If any job did not commit per batch, commit here (we do per batch already)
        return updated_total

    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def main() -> None:
    """
    Usage:
      PYTHONPATH=backend python backend/app/workers/recompute_scores_worker.py

    Default behavior:
      - run once
      - exit with code 0
    """
    updated = worker_once()
    print(f"✅ Worker done. Updated places: {updated}")


if __name__ == "__main__":
    main()