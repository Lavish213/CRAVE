from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.time import normalize_utc
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth


RESOLVER_VERSION = "v2"
MAX_RESOLVED_FROM_LEN = 512


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _freshness_multiplier(created_at: datetime | None) -> float:
    """
    Timezone-safe freshness scoring.
    Safe for:
      - None
      - naive datetimes (assumed UTC)
      - aware datetimes
      - odd sqlite returns via normalize_utc
    """
    if not created_at:
        return 0.5

    created = normalize_utc(created_at)
    if not created:
        return 0.5

    now = _utcnow()

    try:
        age_days = max((now - created).total_seconds() / 86400.0, 0.0)
    except Exception:
        return 0.5

    if age_days < 7:
        return 1.0
    if age_days < 30:
        return 0.85
    if age_days < 90:
        return 0.6
    return 0.4


def _claim_value(claim: PlaceClaim) -> Optional[str]:
    """
    Canonical string key for claim value.
    Deterministic for JSON via sort_keys.
    """
    if getattr(claim, "value_text", None) is not None:
        v = str(claim.value_text).strip()
        return v if v else None

    if getattr(claim, "value_number", None) is not None:
        try:
            return str(float(claim.value_number))
        except Exception:
            return str(claim.value_number)

    if getattr(claim, "value_json", None) is not None:
        try:
            return json.dumps(claim.value_json, sort_keys=True, ensure_ascii=False)
        except Exception:
            return None

    return None


def _safe_resolved_from(payload: list[dict]) -> str:
    """
    PlaceTruth.resolved_from is String(512) in your model.
    Guarantee we never exceed it.
    """
    s = json.dumps(payload, ensure_ascii=False)
    if len(s) <= MAX_RESOLVED_FROM_LEN:
        return s
    # truncate safely (still valid JSON? no — so keep a compact summary)
    # keep minimal audit trail rather than invalid JSON
    return json.dumps(
        {"note": "truncated", "count": len(payload), "sample": payload[:2]},
        ensure_ascii=False,
    )[:MAX_RESOLVED_FROM_LEN]


def resolve_place_truths_v2(
    *,
    db: Session,
    place_id: str,
) -> List[PlaceTruth]:
    """
    Canonical V2 truth resolver.

    - Deterministic winner selection
    - Weight + confidence + freshness aware
    - Idempotent upsert
    - No deletes
    - Timezone safe (SQLite-safe)
    """

    if not place_id:
        return []

    claims: List[PlaceClaim] = (
        db.query(PlaceClaim)
        .filter(PlaceClaim.place_id == place_id)
        .all()
    )

    if not claims:
        return []

    grouped: Dict[str, List[PlaceClaim]] = defaultdict(list)
    for claim in claims:
        field = getattr(claim, "field", None)
        if not field:
            continue
        grouped[str(field)].append(claim)

    resolved_truths: List[PlaceTruth] = []
    now = _utcnow()

    for field, field_claims in grouped.items():
        value_scores: Dict[str, float] = defaultdict(float)
        value_claims: Dict[str, List[PlaceClaim]] = defaultdict(list)

        for claim in field_claims:
            value = _claim_value(claim)
            if not value:
                continue

            conf = _clamp01(getattr(claim, "confidence", 0.0) or 0.0)
            weight = float(getattr(claim, "weight", 1.0) or 1.0)
            freshness = _freshness_multiplier(getattr(claim, "created_at", None))

            base_score = conf * weight

            if bool(getattr(claim, "is_verified_source", False)):
                base_score *= 1.15

            if bool(getattr(claim, "is_user_submitted", False)) and not bool(
                getattr(claim, "is_verified_source", False)
            ):
                base_score *= 0.9

            score = base_score * freshness

            value_scores[value] += score
            value_claims[value].append(claim)

        if not value_scores:
            continue

        total = sum(value_scores.values()) or 1.0
        normalized_scores = {k: (v / total) for k, v in value_scores.items()}

        winner = sorted(
            normalized_scores.items(),
            key=lambda x: (-x[1], x[0]),
        )[0][0]

        confidence = _clamp01(normalized_scores[winner])

        winning_claims = value_claims[winner]
        resolved_from_payload = [
            {
                "claim_id": getattr(c, "id", None),
                "source": getattr(c, "source", None),
                "confidence": getattr(c, "confidence", None),
            }
            for c in winning_claims
        ]
        resolved_from = _safe_resolved_from(resolved_from_payload)

        truth = (
            db.query(PlaceTruth)
            .filter(
                PlaceTruth.place_id == place_id,
                PlaceTruth.truth_type == field,
            )
            .one_or_none()
        )

        if truth:
            truth.truth_value = winner
            truth.confidence = confidence
            truth.resolved_from = resolved_from
            truth.resolver_version = RESOLVER_VERSION
            truth.updated_at = now
        else:
            truth = PlaceTruth(
                place_id=place_id,
                truth_type=field,
                truth_value=winner,
                confidence=confidence,
                resolved_from=resolved_from,
                resolver_version=RESOLVER_VERSION,
                created_at=now,
                updated_at=now,
            )
            db.add(truth)

        resolved_truths.append(truth)

    db.flush()
    return resolved_truths 