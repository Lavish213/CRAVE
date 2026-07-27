from __future__ import annotations

# DEPRECATED / UNUSED: part of the app/services/aoi/* package, written during
# an earlier area-of-interest expansion phase and never wired into any live
# entry point. A grep across the entire backend/ tree found zero imports of
# app.services.aoi.aoi_density or compute_density_score from anywhere.
# Kept here for reference only — not wired up. Safe to delete if no longer needed.

TARGET_DENSITY = 40

def compute_density_score(*, places_in_cell: int) -> float:
    if places_in_cell <= 0:
        return 0.0
    density = places_in_cell / TARGET_DENSITY
    if density > 1.0:
        return 1.0
    return density
