from __future__ import annotations

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
