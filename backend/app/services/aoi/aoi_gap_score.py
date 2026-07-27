from __future__ import annotations

# DEPRECATED / UNUSED: part of the app/services/aoi/* package, written during
# an earlier area-of-interest expansion phase and never wired into any live
# entry point. A grep across the entire backend/ tree found zero imports of
# app.services.aoi.aoi_gap_score or compute_gap_score from anywhere.
# Kept here for reference only — not wired up. Safe to delete if no longer needed.

from typing import Set

def compute_gap_score(*, existing_categories: Set[str], expected_categories: Set[str]) -> float:
    if not expected_categories:
        return 0.0
    missing = expected_categories - existing_categories
    gap_ratio = len(missing) / len(expected_categories)
    if gap_ratio > 1:
        return 1.0
    return gap_ratio
