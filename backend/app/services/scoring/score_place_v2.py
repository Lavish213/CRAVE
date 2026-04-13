from __future__ import annotations

from typing import List

from app.db.models.place import Place
from app.db.models.place_truth import PlaceTruth
from app.services.scoring.weights import (
    SCORE_VERSION,
    CONFIDENCE_WEIGHT,
    STABILITY_WEIGHT,
    VERIFIED_WEIGHT,
    OPERATIONAL_WEIGHT,
    LOCAL_VALIDATION_WEIGHT,
    HYPE_PENALTY_WEIGHT,
    MIN_SCORE,
    MAX_SCORE,
    LOW_CONFIDENCE_THRESHOLD,
    LOW_STABILITY_THRESHOLD,
)


# ============================================================
# Pure Scoring Function
# ============================================================

def score_place_v2(
    *,
    place: Place,
    truths: List[PlaceTruth],
) -> dict:
    """
    Deterministic scoring engine (v2).

    Pure function:
    - No DB writes
    - No session dependency
    - No side effects

    Returns computed score components.
    """

    # ---------------------------------------------------------
    # Aggregate truth signals
    # ---------------------------------------------------------

    if not truths:
        base_confidence = 0.0
        avg_stability = 0.0
        verified_ratio = 0.0
    else:
        base_confidence = sum(t.confidence for t in truths) / len(truths)

        stability_values = [
            t.stability_score for t in truths if t.stability_score is not None
        ]
        avg_stability = (
            sum(stability_values) / len(stability_values)
            if stability_values
            else 0.0
        )

        verified_count = sum(1 for t in truths if t.is_verified)
        verified_ratio = verified_count / len(truths)

    # ---------------------------------------------------------
    # Dampening (low quality protection)
    # ---------------------------------------------------------

    if base_confidence < LOW_CONFIDENCE_THRESHOLD:
        base_confidence *= 0.5

    if avg_stability < LOW_STABILITY_THRESHOLD:
        avg_stability *= 0.5

    # ---------------------------------------------------------
    # Operational Signals
    # ---------------------------------------------------------

    operational_score = 1.0 if place.is_active else 0.0

    # Placeholder for future:
    local_validation_score = place.local_validation or 0.0

    # Hype penalty (inverse relationship)
    hype_penalty = place.hype_penalty or 0.0

    # ---------------------------------------------------------
    # Weighted Composition
    # ---------------------------------------------------------

    composite = (
        (base_confidence * CONFIDENCE_WEIGHT)
        + (avg_stability * STABILITY_WEIGHT)
        + (verified_ratio * VERIFIED_WEIGHT)
        + (operational_score * OPERATIONAL_WEIGHT)
        + (local_validation_score * LOCAL_VALIDATION_WEIGHT)
        - (hype_penalty * HYPE_PENALTY_WEIGHT)
    )

    # Normalize to 0–100 scale
    final_score = composite * 100.0

    # Clamp bounds
    final_score = max(MIN_SCORE, min(MAX_SCORE, final_score))

    return {
        "score_version": SCORE_VERSION,
        "master_score": final_score,
        "confidence_score": base_confidence,
        "operational_confidence": operational_score,
        "local_validation": local_validation_score,
        "hype_penalty": hype_penalty,
        "rank_score": final_score,  # identical for now
    }