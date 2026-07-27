from __future__ import annotations

# DEPRECATED / UNUSED: nothing enqueues to this file-based queue anymore.
# app/scheduler.py's _job_score_recompute now calls
# app.workers.recompute_scores_worker.recompute_places_v4 directly on an
# in-memory batch of stale places, bypassing the queue entirely. A grep
# across the entire backend/ tree found zero imports of
# app.services.enrichment.enqueue (or enqueue_recompute_scores) from
# anywhere, and the matching consumer, app.services.enrichment.worker, is
# equally unreferenced.
# Kept here for reference only — not wired up. Safe to delete if no longer needed.

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ------------------------------------------------------------------
# Queue Location (local dev safe)
# ------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[3]
VAR_DIR = BASE_DIR / "var"
QUEUE_DIR = VAR_DIR / "queue"
QUEUE_FILE = QUEUE_DIR / "recompute_scores.queue"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RecomputeJob:
    type: str
    created_at: str
    payload: Dict[str, Any]


def _ensure_dirs() -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def _append_line(line: str) -> None:
    _ensure_dirs()
    with open(QUEUE_FILE, "a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")


def enqueue_recompute_scores(
    *,
    city_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> RecomputeJob:
    """
    Enqueue a recompute job.

    No DB writes.
    Pure queue append.
    """

    job = RecomputeJob(
        type="recompute_scores",
        created_at=_utcnow_iso(),
        payload={
            "city_id": city_id,
            "limit": limit,
        },
    )

    _append_line(json.dumps(job.__dict__, ensure_ascii=False))
    return job