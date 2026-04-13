from __future__ import annotations

TARGET_DENSITY = 40

def compute_density_score(*, places_in_cell: int) -> float:
    if places_in_cell <= 0:
        return 0.0
    density = places_in_cell / TARGET_DENSITY
    if density > 1.0:
        return 1.0
    return density
