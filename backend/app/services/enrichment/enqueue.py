from __future__ import annotations

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