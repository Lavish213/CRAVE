from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models.visit_evidence import (
    VISIT_TIER_DECLARED,
    VISIT_TIER_VERIFIED,
    VisitEvidence,
)

RANK_ELIGIBLE_TIERS = (VISIT_TIER_DECLARED, VISIT_TIER_VERIFIED)


def upsert_declared_source(
    db: Session,
    *,
    user_id: str,
    place_id: str,
    source: str,
    source_ref: str,
    occurred_at: datetime | None = None,
) -> VisitEvidence:
    """Create/update one source-scoped explicit visit declaration."""
    when = occurred_at or datetime.now(timezone.utc)
    evidence = (
        db.query(VisitEvidence)
        .filter(
            VisitEvidence.user_id == user_id,
            VisitEvidence.place_id == place_id,
            VisitEvidence.source == source,
            VisitEvidence.source_ref == source_ref,
        )
        .one_or_none()
    )
    if evidence is None:
        evidence = VisitEvidence(
            user_id=user_id,
            place_id=place_id,
            tier=VISIT_TIER_DECLARED,
            source=source,
            source_ref=source_ref,
            occurred_at=when,
            confirmed_at=when,
            factual_history=True,
            recommendation_influence=True,
        )
        db.add(evidence)
    else:
        evidence.tier = VISIT_TIER_DECLARED
        evidence.occurred_at = when
        evidence.confirmed_at = when
        evidence.factual_history = True
    return evidence


def retract_source(
    db: Session,
    *,
    user_id: str,
    place_id: str,
    source: str,
    source_ref: str,
) -> int:
    """Retract only the named source; independent visit sources survive."""
    return (
        db.query(VisitEvidence)
        .filter(
            VisitEvidence.user_id == user_id,
            VisitEvidence.place_id == place_id,
            VisitEvidence.source == source,
            VisitEvidence.source_ref == source_ref,
        )
        .delete(synchronize_session=False)
    )


def visit_evidence_for_place(
    db: Session,
    *,
    user_id: str,
    place_id: str,
) -> VisitEvidence | None:
    """
    The single most-recent visit-evidence record for one user/place pair,
    across any tier and any source -- for Place Detail's relationship
    hierarchy (Wave 7), which needs "has this user visited this place at
    all, and how" for exactly one place, not a batch. Existing helpers
    here are batch-oriented (craves.py's graduation query,
    latest_rank_eligible_by_place's Rank Home queue) -- this fills the
    single-place gap rather than making callers filter a batch result.
    """
    return (
        db.query(VisitEvidence)
        .filter(
            VisitEvidence.user_id == user_id,
            VisitEvidence.place_id == place_id,
        )
        .order_by(VisitEvidence.occurred_at.desc(), VisitEvidence.created_at.desc())
        .first()
    )


def latest_rank_eligible_by_place(
    db: Session,
    *,
    user_id: str,
    limit: int = 50,
) -> list[VisitEvidence]:
    """
    Latest declared/verified evidence per place, newest first.

    Multiple factual visits are retained; Rank Home only needs one queue row per
    unranked place, so deduplication happens at this read boundary rather than
    destroying visit history in storage.
    """
    rows = (
        db.query(VisitEvidence)
        .filter(
            VisitEvidence.user_id == user_id,
            VisitEvidence.factual_history.is_(True),
            VisitEvidence.tier.in_(RANK_ELIGIBLE_TIERS),
        )
        .order_by(VisitEvidence.occurred_at.desc(), VisitEvidence.created_at.desc())
        .limit(max(limit * 4, limit))
        .all()
    )
    seen: set[str] = set()
    out: list[VisitEvidence] = []
    for row in rows:
        if row.place_id in seen:
            continue
        seen.add(row.place_id)
        out.append(row)
        if len(out) >= limit:
            break
    return out
