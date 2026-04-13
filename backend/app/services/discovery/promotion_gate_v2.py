from __future__ import annotations

from typing import Dict, Any, Tuple


# ---------------------------------------------------
# CONFIG
# ---------------------------------------------------

MIN_CONFIDENCE_THRESHOLD = 0.72


# ---------------------------------------------------
# Safe coercion helpers
# ---------------------------------------------------

def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        v = float(value)
        if v != v:  # NaN guard
            return default
        return v
    except Exception:
        return default


def _status(candidate: Dict[str, Any]) -> str:
    return str(candidate.get("status") or "").lower()


# ---------------------------------------------------
# Promotion Gate (V2 - ORM Aligned)
# ---------------------------------------------------

def can_promote_candidate_v2(candidate: Dict[str, Any]) -> bool:
    ok, _ = explain_promotion_gate_v2(candidate)
    return ok


def explain_promotion_gate_v2(
    candidate: Dict[str, Any]
) -> Tuple[bool, Dict[str, Any]]:
    """
    V2 Promotion Hard Gates

    Rules:
    - must not be blocked
    - must not already promoted
    - must not already resolved
    - must meet confidence threshold
    """

    blocked = bool(candidate.get("blocked", False))
    status = _status(candidate)
    resolved = bool(candidate.get("resolved", False))
    resolved_place_id = candidate.get("resolved_place_id")

    confidence = _to_float(candidate.get("confidence_score"))

    if blocked:
        return False, {"reason": "blocked"}

    if status == "promoted":
        return False, {"reason": "already_promoted"}

    if resolved or resolved_place_id:
        return False, {"reason": "already_resolved"}

    if confidence < MIN_CONFIDENCE_THRESHOLD:
        return False, {
            "reason": "low_confidence",
            "confidence": confidence,
            "threshold": MIN_CONFIDENCE_THRESHOLD,
        }

    return True, {
        "reason": "eligible",
        "confidence": confidence,
    }