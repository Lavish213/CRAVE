from __future__ import annotations
from typing import Set

def compute_gap_score(*, existing_categories: Set[str], expected_categories: Set[str]) -> float:
    if not expected_categories:
        return 0.0
    missing = expected_categories - existing_categories
    gap_ratio = len(missing) / len(expected_categories)
    if gap_ratio > 1:
        return 1.0
    return gap_ratio
