from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy.orm import Session

from app.db.models.place import Place


# =========================================================
# Deterministic Micro Entropy (Tie Break Only)
# =========================================================

def _entropy_from_uuid(place_id: str | None) -> float:
    if not place_id:
        return 0.0

    try:
        hex_tail = place_id.replace("-", "")[-6:]
        value = int(hex_tail, 16) % 1000
        return value / 1_000_000
    except Exception:
        return 0.0


def _utcnow():
    return datetime.now(timezone.utc)


# =========================================================
# Phase 1 Deterministic Master Score
# =========================================================

def _compute_master_score(place: Place) -> float:
    """
    Phase 1 scoring:
    Purely based on persisted fields.
    No ingestion dependency.
    """

    base = 0.0

    base += place.confidence_score or 0.0
    base += place.operational_confidence or 0.0
    base += place.local_validation or 0.0

    base -= place.hype_penalty or 0.0

    return float(base)


# =========================================================
# Production Recompute Engine (Phase 1 Stable)
# =========================================================

def recompute_place_scores(
    db: Session,
    *,
    places: Iterable[Place],
) -> int:
    """
    Deterministic recompute engine.

    Guarantees:
        - No commits
        - No ingestion dependency
        - Deterministic ordering via UUID entropy
        - Stable across SQLite/Postgres
    """

    updated = 0

    for place in places:

        place_id = getattr(place, "id", None)
        if not place_id:
            continue

        # ---------------------------------------------------------
        # 1️⃣ Compute Master Score (Self-Contained)
        # ---------------------------------------------------------

        master_score = _compute_master_score(place)

        # ---------------------------------------------------------
        # 2️⃣ Rank Score (Projection = master for Phase 1)
        # ---------------------------------------------------------

        rank_score = master_score

        # ---------------------------------------------------------
        # 3️⃣ Deterministic Tie Break
        # ---------------------------------------------------------

        entropy = _entropy_from_uuid(place_id)

        final_rank_score = rank_score + entropy
        final_rank_score = round(float(final_rank_score), 6)

        # ---------------------------------------------------------
        # 4️⃣ Persist
        # ---------------------------------------------------------

        place.master_score = master_score
        place.rank_score = final_rank_score
        place.last_scored_at = _utcnow()

        updated += 1

    return updated