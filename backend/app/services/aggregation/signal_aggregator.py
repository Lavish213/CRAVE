from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, List

from sqlalchemy.orm import Session

from app.db.models.place import Place
from app.db.models.place_signal import PlaceSignal


# --------------------------------------------------
# TIME
# --------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# --------------------------------------------------
# NORMALIZATION HELPERS
# --------------------------------------------------

def _clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    return max(0.0, min(1.0, v))


# --------------------------------------------------
# SIGNAL WEIGHTS (CORE LOGIC)
# --------------------------------------------------

SIGNAL_WEIGHTS: Dict[str, float] = {
    "rating": 1.0,
    "review_count": 0.7,
    "mention": 0.6,
    "save": 0.8,
    "trending": 1.2,
    "open_now": 0.3,
}


PROVIDER_WEIGHTS: Dict[str, float] = {
    "google": 1.0,
    "yelp": 1.0,
    "tiktok": 0.9,
    "internal": 1.1,
}


# --------------------------------------------------
# CORE AGGREGATION
# --------------------------------------------------

def aggregate_place_signals(
    *,
    db: Session,
    place_id: str,
) -> Place | None:

    if not place_id:
        return None

    place: Place | None = (
        db.query(Place)
        .filter(Place.id == place_id)
        .one_or_none()
    )

    if not place:
        return None

    signals: List[PlaceSignal] = (
        db.query(PlaceSignal)
        .filter(PlaceSignal.place_id == place_id)
        .all()
    )

    if not signals:
        return place

    # --------------------------------------------------
    # AGGREGATION BUCKETS
    # --------------------------------------------------

    total_score = 0.0
    total_weight = 0.0

    operational_score = 0.0
    validation_score = 0.0
    hype_score = 0.0

    for s in signals:

        signal_type = getattr(s, "signal_type", None)
        provider = getattr(s, "provider", None)

        base_value = _clamp01(getattr(s, "value", 0.0))

        signal_weight = SIGNAL_WEIGHTS.get(signal_type, 0.5)
        provider_weight = PROVIDER_WEIGHTS.get(provider, 0.8)

        weight = signal_weight * provider_weight

        score = base_value * weight

        total_score += score
        total_weight += weight

        # --------------------------------------------------
        # SUB-SCORES
        # --------------------------------------------------

        if signal_type in {"rating", "review_count"}:
            validation_score += score

        if signal_type in {"open_now"}:
            operational_score += score

        if signal_type in {"mention", "trending"}:
            hype_score += score

    # --------------------------------------------------
    # FINAL SCORES
    # --------------------------------------------------

    master_score = total_score / total_weight if total_weight > 0 else 0.0

    confidence_score = _clamp01(master_score)

    operational_confidence = _clamp01(operational_score / (total_weight or 1.0))

    local_validation = _clamp01(validation_score / (total_weight or 1.0))

    hype_penalty = _clamp01(hype_score / (total_weight or 1.0))

    # --------------------------------------------------
    # FINAL RANK SCORE
    # --------------------------------------------------

    rank_score = (
        (confidence_score * 0.5)
        + (local_validation * 0.3)
        + (operational_confidence * 0.2)
        - (hype_penalty * 0.25)
    )

    rank_score = _clamp01(rank_score)

    # --------------------------------------------------
    # UPDATE PLACE
    # --------------------------------------------------

    now = _utcnow()

    place.master_score = float(master_score)
    place.confidence_score = float(confidence_score)
    place.operational_confidence = float(operational_confidence)
    place.local_validation = float(local_validation)
    place.hype_penalty = float(hype_penalty)
    place.rank_score = float(rank_score)

    place.last_scored_at = now
    place.needs_recompute = False

    db.flush()

    return place


# --------------------------------------------------
# BULK AGGREGATION (WORKER SAFE)
# --------------------------------------------------

def aggregate_places_bulk(
    *,
    db: Session,
    place_ids: List[str],
) -> int:

    if not place_ids:
        return 0

    updated = 0

    for pid in place_ids:
        result = aggregate_place_signals(db=db, place_id=pid)
        if result:
            updated += 1

    return updated