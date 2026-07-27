from __future__ import annotations

# DEPRECATED / UNUSED: part of the app/services/aoi/* package, written during
# an earlier area-of-interest expansion phase and never wired into any live
# entry point. A grep across the entire backend/ tree found zero imports of
# app.services.aoi.aoi_velocity or compute_velocity_score from anywhere.
# Kept here for reference only — not wired up. Safe to delete if no longer needed.

def compute_velocity_score(*, saves: int, views: int, searches: int) -> float:
    score = (
        saves * 0.5 +
        views * 0.3 +
        searches * 0.2
    )
    normalized = score / 100
    if normalized > 1.0:
        return 1.0
    return normalized
