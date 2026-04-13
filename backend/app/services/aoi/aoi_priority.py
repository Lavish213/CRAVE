from __future__ import annotations

WEIGHT_DENSITY_GAP = 0.45
WEIGHT_SAVE_VELOCITY = 0.35
WEIGHT_GAP_SCORE = 0.20

BASE_PRIORITY = 0.30
MAX_PRIORITY = 1.00

def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v

def compute_aoi_priority(density_score: float, save_velocity: float, gap_score: float) -> float:
    density_gap = 1.0 - _clamp(density_score)

    priority = (
        BASE_PRIORITY +
        density_gap * WEIGHT_DENSITY_GAP +
        _clamp(save_velocity) * WEIGHT_SAVE_VELOCITY +
        _clamp(gap_score) * WEIGHT_GAP_SCORE
    )

    return _clamp(priority,0.0,MAX_PRIORITY)

def classify_priority(priority: float) -> str:
    p = _clamp(priority)

    if p >= 0.85:
        return "critical"

    if p >= 0.70:
        return "high"

    if p >= 0.50:
        return "elevated"

    if p >= 0.30:
        return "normal"

    return "low"
