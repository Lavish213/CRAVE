from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from sqlalchemy.orm import Session

from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.discovery.promote_service_v2 import promote_candidate_v2


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

MAX_PROMOTIONS_PER_RUN = 50
MIN_CONFIDENCE_THRESHOLD = 0.72


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def promote_ready_candidates_v2(
    *,
    db: Session,
    limit: int = MAX_PROMOTIONS_PER_RUN,
) -> int:
    """
    V2 Promotion Orchestrator (Production Locked)

    - Filters eligible candidates at DB level
    - Enforces confidence threshold
    - Skips blocked
    - Skips already resolved
    - Promotes in controlled batches
    - Commits once per run
    - Rolls back per failure
    - Fully idempotent
    """

    if not limit or limit <= 0:
        return 0

    # Oversample in case some promotions fail
    candidates: List[DiscoveryCandidate] = (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.status == "candidate")
        .filter(DiscoveryCandidate.resolved.is_(False))
        .filter(DiscoveryCandidate.blocked.is_(False))
        .filter(
            DiscoveryCandidate.confidence_score >= MIN_CONFIDENCE_THRESHOLD
        )
        .order_by(DiscoveryCandidate.created_at.asc())
        .limit(limit * 2)
        .all()
    )

    if not candidates:
        return 0

    promoted_count = 0

    for candidate in candidates:
        if promoted_count >= limit:
            break

        try:
            place_id = promote_candidate_v2(
                db=db,
                candidate_id=candidate.id,
            )

            if place_id:
                promoted_count += 1

        except Exception:
            # isolate failure — do not kill batch
            db.rollback()
            continue

    if promoted_count > 0:
        db.commit()

    return promoted_count