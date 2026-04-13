from __future__ import annotations

from typing import List, Tuple
from datetime import datetime, timezone
import math

from app.db.models.place_claim import PlaceClaim


UTC = timezone.utc


def _safe_float(value: float | None, default: float = 0.0) -> float:
    try:
        v = float(value)

        if math.isnan(v) or math.isinf(v):
            return default

        return v

    except Exception:
        return default


def _freshness_bonus(claim: PlaceClaim) -> float:

    payload = getattr(claim, "value_json", None)

    if not isinstance(payload, dict):
        return 1.0

    ts = payload.get("ingested_at")

    if not ts:
        return 1.0

    try:
        dt = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=UTC)

    except Exception:
        return 1.0

    now = datetime.now(UTC)

    age_days = max((now - dt).days, 0)

    if age_days < 1:
        return 1.10

    if age_days < 7:
        return 1.05

    if age_days < 30:
        return 1.02

    return 1.0


def _source_type_weight(claim: PlaceClaim) -> float:

    payload = getattr(claim, "value_json", None)

    if not isinstance(payload, dict):
        return 1.0

    source_type = payload.get("source_type")

    if source_type == "provider_api":
        return 1.2

    if source_type == "official_html":
        return 1.0

    if source_type == "scraped_html":
        return 0.7

    if source_type == "fallback":
        return 0.5

    return 1.0


def score_claim(claim: PlaceClaim) -> float:

    confidence = _safe_float(getattr(claim, "confidence", None), 0.5)
    weight = _safe_float(getattr(claim, "weight", None), 1.0)

    score = confidence * weight

    score *= _source_type_weight(claim)

    if getattr(claim, "is_verified_source", False):
        score *= 1.15

    if getattr(claim, "is_user_submitted", False) and not getattr(
        claim,
        "is_verified_source",
        False,
    ):
        score *= 0.9

    score *= _freshness_bonus(claim)

    if math.isnan(score) or math.isinf(score):
        return 0.0

    return max(score, 0.0)


def score_candidate_group(
    claims: List[PlaceClaim],
) -> Tuple[PlaceClaim, float]:

    if not claims:
        raise ValueError("Cannot score empty claim group")

    scored = []
    total = 0.0

    for claim in claims:

        s = score_claim(claim)

        scored.append((claim, s))

        total += s

    if total <= 0:
        return claims[0], 0.0

    scored.sort(
        key=lambda x: (
            x[1],
            getattr(x[0], "created_at", None) or datetime.min.replace(tzinfo=UTC),
        ),
        reverse=True,
    )

    winner, winner_score = scored[0]

    normalized_confidence = winner_score / total

    if normalized_confidence < 0:
        normalized_confidence = 0.0

    if normalized_confidence > 1:
        normalized_confidence = 1.0

    return winner, normalized_confidence