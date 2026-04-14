from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Any, List

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_truth import PlaceTruth
from app.services.scoring.score_place_v2 import score_place_v2


DEFAULT_BATCH_LIMIT = 200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def score_all_places_v2(
    *,
    db: Session,
    limit: int = DEFAULT_BATCH_LIMIT,
) -> Dict[str, Any]:
    # ⚠️  ORPHANED PATH — reads as of Phase 3 audit (2026-04-13):
    #
    # This function is only triggered when Place.needs_recompute = True.
    # As of Phase 3, NOTHING in the active pipeline sets that flag,
    # so this function always returns {"scored": 0, "attempted": 0, ...}.
    #
    # The ACTIVE scoring path is:
    #   recompute_scores_worker.py → recompute.py → recompute_place_scores()
    #
    # ⚠️  SCALE CONFLICT: this function produces scores on a 0–100 scale
    # (via score_place_v2 → weights.py). recompute_place_scores() produces
    # raw ~0–3 floats. Both write to Place.master_score / Place.rank_score.
    # DO NOT activate both simultaneously — scores become incomparable.
    #
    # To activate this path intentionally:
    #   1. Set Place.needs_recompute = True on target records
    #   2. Decide whether to standardize to 0–1 or 0–100 across both paths
    #   3. Run recompute_scores_worker.py in queue mode
    """
    V2 Batch Scoring Orchestrator

    Responsibilities:
    - Pull Places needing recompute
    - Fetch truths
    - Compute scores via pure scorer
    - Persist results
    - Clear needs_recompute
    - Commit once per batch
    - Rollback per-place on failure

    Returns stats for logs/monitoring.
    """

    if not limit or limit <= 0:
        return {"scored": 0, "attempted": 0, "failed": 0, "limit": limit}

    places: List[Place] = (
        db.query(Place)
        .filter(Place.needs_recompute.is_(True))
        .order_by(Place.updated_at.asc())
        .limit(limit)
        .all()
    )

    attempted = len(places)
    if attempted == 0:
        return {"scored": 0, "attempted": 0, "failed": 0, "limit": limit}

    scored = 0
    failed = 0
    now = _utcnow()

    for p in places:
        try:
            truths: List[PlaceTruth] = (
                db.query(PlaceTruth)
                .filter(PlaceTruth.place_id == p.id)
                .all()
            )

            computed = score_place_v2(place=p, truths=truths)

            p.master_score = float(computed["master_score"])
            p.confidence_score = float(computed["confidence_score"])
            p.operational_confidence = float(computed["operational_confidence"])
            p.local_validation = float(computed["local_validation"])
            p.hype_penalty = float(computed["hype_penalty"])
            p.rank_score = float(computed["rank_score"])

            p.score_version = int(computed["score_version"])
            p.last_scored_at = now
            p.needs_recompute = False

            db.flush()
            scored += 1

        except Exception:
            db.rollback()
            failed += 1
            continue

    if scored > 0:
        db.commit()

    return {
        "attempted": attempted,
        "scored": scored,
        "failed": failed,
        "limit": limit,
    }