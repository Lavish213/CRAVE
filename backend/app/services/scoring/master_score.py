from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime, timezone


# =========================================================
# SCORING CONFIG (V2 — configurable, not hardcoded)
# =========================================================

SCORING_VERSION = 1

SCORING_WEIGHTS = {
    # Base quality composition
    "taste_weight": 0.72,
    "confidence_weight": 0.28,

    # Trust layer composition
    "ops_weight": 0.45,
    "local_weight": 0.35,
    "confidence_trust_weight": 0.20,

    # Hype penalty multiplier
    "hype_penalty_weight": 0.35,
}


# =========================================================
# Utilities
# =========================================================

def clamp(value: float | None, lo: float = 0.0, hi: float = 1.0) -> float:
    if value is None:
        return lo
    return max(lo, min(hi, float(value)))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# =========================================================
# Result Object
# =========================================================

@dataclass
class MasterScoreResult:
    master_score: float
    confidence_score: float
    operational_confidence: float
    local_validation: float
    hype_penalty: float
    score_version: int
    computed_at: datetime
    breakdown: Dict[str, Any]


# =========================================================
# Core Engine
# =========================================================

def compute_master_score(
    *,
    taste_score: float,
    confidence_score: float,
    operational_confidence: float,
    local_validation: float,
    hype_penalty: float,
) -> MasterScoreResult:
    """
    Deterministic scoring engine (Lean V2).

    Inputs:
        taste_score: 0–5 scale
        confidence_score: 0–1
        operational_confidence: 0–1
        local_validation: 0–1
        hype_penalty: 0–1

    Returns:
        MasterScoreResult
    """

    # -----------------------------------------------------
    # Normalize Inputs
    # -----------------------------------------------------

    taste = clamp((taste_score or 0.0) / 5.0)
    confidence = clamp(confidence_score)
    ops = clamp(operational_confidence)
    local = clamp(local_validation)
    hype = clamp(hype_penalty)

    # -----------------------------------------------------
    # Base Quality
    # -----------------------------------------------------

    base_quality = (
        (taste * SCORING_WEIGHTS["taste_weight"]) +
        (confidence * SCORING_WEIGHTS["confidence_weight"])
    )

    # -----------------------------------------------------
    # Trust Multiplier
    # -----------------------------------------------------

    trust_factor = (
        (ops * SCORING_WEIGHTS["ops_weight"]) +
        (local * SCORING_WEIGHTS["local_weight"]) +
        (confidence * SCORING_WEIGHTS["confidence_trust_weight"])
    )

    trusted_quality = base_quality * (0.75 + 0.25 * trust_factor)

    # -----------------------------------------------------
    # Hype Penalty
    # -----------------------------------------------------

    penalty_multiplier = 1.0 - (hype * SCORING_WEIGHTS["hype_penalty_weight"])

    master_score = clamp(trusted_quality * penalty_multiplier)

    # -----------------------------------------------------
    # Return Structured Result
    # -----------------------------------------------------

    return MasterScoreResult(
        master_score=round(master_score, 6),
        confidence_score=confidence,
        operational_confidence=ops,
        local_validation=local,
        hype_penalty=hype,
        score_version=SCORING_VERSION,
        computed_at=utcnow(),
        breakdown={
            "taste_normalized": taste,
            "base_quality": base_quality,
            "trust_factor": trust_factor,
            "trusted_quality": trusted_quality,
            "penalty_multiplier": penalty_multiplier,
        },
    )