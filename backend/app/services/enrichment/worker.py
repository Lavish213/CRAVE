from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.services.scoring.recompute import recompute_place_scores


# ------------------------------------------------------------------
# Queue Location (must match enqueue.py)
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[3]
VAR_DIR = BASE_DIR / "var"
QUEUE_DIR = VAR_DIR / "queue"
QUEUE_FILE = QUEUE_DIR / "recompute_scores.queue"


@dataclass(frozen=True)
class Job:
    type: str
    created_at: str
    payload: Dict[str, Any]


def _read_jobs() -> list[Job]:
    if not QUEUE_FILE.exists():
        return []

    raw = QUEUE_FILE.read_text(encoding="utf-8").strip()
    if not raw:
        return []

    jobs: list[Job] = []

    for line in raw.splitlines():
        data = json.loads(line)
        jobs.append(
            Job(
                type=str(data.get("type")),
                created_at=str(data.get("created_at")),
                payload=dict(data.get("payload") or {}),
            )
        )

    return jobs


def _clear_queue() -> None:
    QUEUE_FILE.write_text("", encoding="utf-8")


def _clamp_limit(limit: Optional[int]) -> Optional[int]:
    if limit is None:
        return None
    try:
        return max(1, int(limit))
    except Exception:
        return None


def _iter_places(
    db: Session,
    *,
    city_id: Optional[str],
    limit: Optional[int],
    batch_size: int = 500,
):
    limit = _clamp_limit(limit)

    stmt = select(Place).order_by(Place.id.asc())

    if city_id:
        stmt = stmt.where(Place.city_id == city_id)

    offset = 0
    processed = 0

    while True:
        batch = db.execute(
            stmt.limit(batch_size).offset(offset)
        ).scalars().all()

        if not batch:
            break

        if limit is not None:
            remaining = limit - processed
            if remaining <= 0:
                break
            if len(batch) > remaining:
                batch = batch[:remaining]

        yield batch

        processed += len(batch)
        offset += batch_size

        if limit is not None and processed >= limit:
            break


def run_worker_once() -> int:
    """
    Process all queued jobs once.
    Deterministic.
    No randomness.
    """

    jobs = _read_jobs()

    if not jobs:
        return 0

    _clear_queue()

    db = SessionLocal()
    total_updated = 0

    try:
        for job in jobs:
            if job.type != "recompute_scores":
                continue

            city_id = job.payload.get("city_id")
            limit = job.payload.get("limit")

            for batch in _iter_places(
                db,
                city_id=city_id,
                limit=limit,
                batch_size=500,
            ):
                updated = recompute_place_scores(db, places=batch)
                total_updated += updated
                db.commit()

        return total_updated

    except Exception:
        db.rollback()
        raise

    finally:
        db.close()