from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

# ------------------------------------------------------------
# Queue location (repo-local, safe for dev)
# ------------------------------------------------------------

# backend/app/workers/enqueue_recompute_scores.py -> parents[2] == backend/app
APP_DIR = Path(__file__).resolve().parents[2]
VAR_DIR = APP_DIR / "var"
QUEUE_DIR = VAR_DIR / "queue"
QUEUE_FILE = QUEUE_DIR / "recompute_scores.queue"


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class RecomputeScoresJob:
    """
    Append-only queue job.
    Worker is the only consumer.

    NOTE: This is a file queue (no DB schema).
    Replace later with a DB queue / Redis / etc without changing the worker contract.
    """
    type: str
    created_at: str
    payload: Dict[str, Any]


def _ensure_dirs() -> None:
    QUEUE_DIR.mkdir(parents=True, exist_ok=True)


def _append_line_atomic(path: Path, line: str) -> None:
    """
    Append one line atomically-ish (single write).
    Good enough for dev; if you later need concurrency, we can add OS-level locking.
    """
    _ensure_dirs()
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)
        f.write("\n")


def enqueue_recompute_scores(
    *,
    city_id: Optional[str] = None,
    limit: Optional[int] = None,
) -> RecomputeScoresJob:
    job = RecomputeScoresJob(
        type="recompute_scores",
        created_at=_utcnow_iso(),
        payload={
            "city_id": city_id,
            "limit": limit,
        },
    )

    _append_line_atomic(QUEUE_FILE, json.dumps(job.__dict__, ensure_ascii=False))
    return job


def main() -> None:
    """
    Usage:
      PYTHONPATH=backend python backend/app/workers/enqueue_recompute_scores.py
      PYTHONPATH=backend python backend/app/workers/enqueue_recompute_scores.py <city_id>
      PYTHONPATH=backend python backend/app/workers/enqueue_recompute_scores.py <city_id> <limit>
    """
    city_id: Optional[str] = None
    limit: Optional[int] = None

    if len(sys.argv) >= 2:
        city_id = sys.argv[1] or None

    if len(sys.argv) >= 3:
        raw_limit = sys.argv[2]
        try:
            limit = int(raw_limit)
        except Exception:
            print("❌ limit must be an integer")
            raise SystemExit(2)

    job = enqueue_recompute_scores(city_id=city_id, limit=limit)
    print("✅ Enqueued recompute_scores job")
    print(f"   queue_file: {QUEUE_FILE}")
    print(f"   job: {job.type} payload={job.payload}")


if __name__ == "__main__":
    main()