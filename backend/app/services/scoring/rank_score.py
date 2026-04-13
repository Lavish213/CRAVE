from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


# =========================================================
# RANK CONFIG (Projection Layer Only)
# =========================================================
# NOTE:
# - No versioning here.
# - Version is owned by master_score layer.
# - Ranking is a deterministic projection of master_score.
# =========================================================

RANK_CONFIG = {
    "proximity_weight": 0.10,
    "personalization_weight": 0.15,
    "trending_weight": 0.12,
    "max_boost_cap": 0.35,
    "decay_enabled": False,  # placeholder for future time decay
}


# =========================================================
# Utilities
# =========================================================

def clamp(value: float | None, lo: float = 0.0, hi: float = 1.0) -> float:
    if value is None:
        return lo
    return max(lo, min(hi, float(value)))


# =========================================================
# Result Object
# =========================================================

@dataclass(frozen=True)
class RankScoreResult:
    rank_score: float
    breakdown: Dict[str, Any]


# =========================================================
# Core Ranking Engine
# =========================================================

def compute_rank_score(
    *,
    master_score: float | None,
    proximity_signal: float = 0.0,
    personalization_signal: float = 0.0,
    trending_signal: float = 0.0,
) -> RankScoreResult:
    """
    Production ranking projection.

    rank_score = master_score + capped_weighted_boost

    Guarantees:
    - Deterministic
    - Pure function
    - No side effects
    - No version ownership
    - Safe 0–1 normalization
    """

    base = clamp(master_score)

    # Normalize signals
    proximity = clamp(proximity_signal)
    personalization = clamp(personalization_signal)
    trending = clamp(trending_signal)

    # Weighted boost
    raw_boost = (
        proximity * RANK_CONFIG["proximity_weight"]
        + personalization * RANK_CONFIG["personalization_weight"]
        + trending * RANK_CONFIG["trending_weight"]
    )

    capped_boost = min(raw_boost, RANK_CONFIG["max_boost_cap"])

    # Final rank score (bounded)
    final_score = clamp(base + capped_boost)

    return RankScoreResult(
        rank_score=round(final_score, 6),
        breakdown={
            "base_master_score": base,
            "proximity_signal": proximity,
            "personalization_signal": personalization,
            "trending_signal": trending,
            "raw_boost": raw_boost,
            "capped_boost": capped_boost,
        },
    )