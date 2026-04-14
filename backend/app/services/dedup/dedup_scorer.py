from __future__ import annotations

from typing import Optional

from app.services.entity.dedupe_rules import compute_match_score, HIGH_CONFIDENCE

MERGE_THRESHOLD = HIGH_CONFIDENCE        # 0.92 — auto-merge safe
REVIEW_THRESHOLD = 0.80                  # flag for review


def score_place_pair(
    *,
    name_a: str,
    name_b: str,
    addr_a: Optional[str] = None,
    addr_b: Optional[str] = None,
    lat_a: Optional[float] = None,
    lng_a: Optional[float] = None,
    lat_b: Optional[float] = None,
    lng_b: Optional[float] = None,
) -> float:
    """Return a [0, 1] similarity score for two places."""
    return compute_match_score(
        name_a=name_a,
        name_b=name_b,
        addr_a=addr_a,
        addr_b=addr_b,
        lat_a=lat_a,
        lng_a=lng_a,
        lat_b=lat_b,
        lng_b=lng_b,
    )


def is_auto_merge(score: float) -> bool:
    return score >= MERGE_THRESHOLD


def is_review_candidate(score: float) -> bool:
    return REVIEW_THRESHOLD <= score < MERGE_THRESHOLD
