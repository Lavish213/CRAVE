from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import List

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.discovery.promote_service_v2 import promote_candidate_v2

logger = logging.getLogger(__name__)


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

MAX_PROMOTIONS_PER_RUN = 50
MIN_CONFIDENCE_THRESHOLD = 0.72

# Failure handling — previously a promotion failure was caught, rolled back,
# and completely discarded: no logging, no counter, no backoff. A candidate
# with e.g. a bad address encoding would be retried every 5-minute discovery
# cycle forever with zero visibility that it was permanently stuck.
MAX_FAILURES_BEFORE_BLOCK = 5
BACKOFF_BASE_MINUTES = 5  # retry delay = base * 2^(failure_count-1), capped below
BACKOFF_MAX_MINUTES = 240


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

    now = _utcnow()

    # Oversample in case some promotions fail
    candidates: List[DiscoveryCandidate] = (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.status.in_(["candidate", "raw"]))
        .filter(DiscoveryCandidate.resolved.is_(False))
        .filter(DiscoveryCandidate.blocked.is_(False))
        .filter(
            DiscoveryCandidate.confidence_score >= MIN_CONFIDENCE_THRESHOLD
        )
        # Skip candidates still in backoff from a previous failure.
        .filter(
            or_(
                DiscoveryCandidate.next_retry_at.is_(None),
                DiscoveryCandidate.next_retry_at <= now,
            )
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

            # Commit after each successful promotion to isolate failures.
            db.commit()

        except Exception as exc:
            # Rollback only undoes the current candidate's changes.
            db.rollback()

            # Record the failure instead of silently discarding it — this is
            # the fix for candidates being retried forever with no trace.
            try:
                candidate.failure_count = (candidate.failure_count or 0) + 1
                candidate.last_error = str(exc)[:500]

                if candidate.failure_count >= MAX_FAILURES_BEFORE_BLOCK:
                    candidate.blocked = True
                    logger.error(
                        "candidate_dead_lettered candidate_id=%s name=%s "
                        "failure_count=%s last_error=%s",
                        candidate.id, candidate.name,
                        candidate.failure_count, candidate.last_error,
                    )
                else:
                    delay_minutes = min(
                        BACKOFF_BASE_MINUTES * (2 ** (candidate.failure_count - 1)),
                        BACKOFF_MAX_MINUTES,
                    )
                    candidate.next_retry_at = now + timedelta(minutes=delay_minutes)
                    logger.warning(
                        "candidate_promotion_failed candidate_id=%s name=%s "
                        "failure_count=%s retry_in_min=%s error=%s",
                        candidate.id, candidate.name,
                        candidate.failure_count, delay_minutes, exc,
                    )

                db.commit()
            except Exception:
                # Bookkeeping itself failed — don't let that crash the run.
                logger.exception(
                    "candidate_failure_tracking_failed candidate_id=%s", candidate.id
                )
                db.rollback()

            continue

    return promoted_count