# app/services/scoring/place_score_v4.py
#
# V4 scoring model — 5-bucket architecture with consensus-gated creator signals.
# Do NOT import place_score_v3; helpers are copied here intentionally.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from app.services.scoring.city_weight_profiles import get_profile

_ENTROPY_DIV = 1_000_000_000_000


# ---------------------------------------------------------------------------
# Helpers (copied from v3 — v3 is not imported)
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _clamp(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _uuid_entropy(place_id: str) -> float:
    try:
        return (int(place_id.replace("-", "")[-6:], 16) % 1_000_000) / _ENTROPY_DIV
    except Exception:
        return 0.0


def _recency(updated_at: Optional[datetime]) -> float:
    if updated_at is None:
        return 0.0
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    days = (_utcnow() - updated_at).total_seconds() / 86400.0
    raw = 1.0 - days / 90.0
    # Snap to exact 1.0 for very fresh timestamps (within 1 second)
    if days < 1 / 86400.0:
        return 1.0
    return _clamp(raw)


def _completeness(
    *,
    name: str,
    lat: Optional[float],
    lng: Optional[float],
    has_image: bool,
    has_menu: bool,
    website: Optional[str],
) -> float:
    checks = [
        bool((name or "").strip()),
        lat is not None and lng is not None,
        has_image,
        has_menu or bool((website or "").strip()),
    ]
    return sum(checks) / len(checks)


def _redistribute_weights(
    weights: Dict[str, float],
    signals: Dict[str, float],
) -> Dict[str, float]:
    """Redistribute weight from zero-value signals to active signals.

    Only keys present in *weights* that are also in *signals* are considered;
    keys absent from *weights* (e.g. risk) are never touched.
    """
    has_data = {k for k, v in signals.items() if v > 0.0}
    if not has_data:
        return weights
    missing_weight = sum(weights[k] for k in weights if k not in has_data)
    if missing_weight == 0.0:
        return weights
    active_total = sum(weights[k] for k in has_data)
    if active_total == 0.0:
        return weights
    result = {}
    for k, w in weights.items():
        if k in has_data:
            result[k] = w + (w / active_total) * missing_weight
        else:
            result[k] = 0.0
    return result


# ---------------------------------------------------------------------------
# Consensus gate for creator signal (v4 new)
# ---------------------------------------------------------------------------

def _apply_consensus_gate(creator_score: float, creator_mention_count: int) -> float:
    """Gate creator_score by how many distinct creators have mentioned the place.

    < 2 mentions  → 0.0   (discovery signal only, no ranking effect)
    == 2 mentions → 50 %  (partial weight)
    >= 3 mentions → full  (trusted consensus)
    """
    if creator_mention_count < 2:
        return 0.0
    if creator_mention_count == 2:
        return creator_score * 0.5
    return creator_score  # >= 3


# ---------------------------------------------------------------------------
# 5-bucket functions
# ---------------------------------------------------------------------------

def compute_structural(signals: Dict[str, float], weights: Dict[str, float]) -> float:
    """Weighted sum of data-quality signals: menu, image, completeness, app."""
    keys = ("menu_score", "image_score", "completeness_score", "app_score")
    return sum(signals[k] * weights[k] for k in keys)


def compute_authenticity(signals: Dict[str, float], weights: Dict[str, float]) -> float:
    """Weighted sum of community/editorial signals: hitlist, creator (gated), blog."""
    keys = ("hitlist_score", "creator_score", "blog_score")
    return sum(signals[k] * weights[k] for k in keys)


def compute_authority(signals: Dict[str, float], weights: Dict[str, float]) -> float:
    """Weighted sum of third-party authority signals: awards only."""
    return signals["awards_score"] * weights["awards_score"]


def compute_momentum(signals: Dict[str, float], weights: Dict[str, float]) -> float:
    """Weighted sum of freshness signals: recency only."""
    return signals["recency_score"] * weights["recency_score"]


def compute_risk(risk_score: float, risk_weight: float) -> float:
    """Risk deduction — structure exists, value is 0.0 until risk data is available."""
    return risk_score * risk_weight


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreV4Result:
    final_score: float
    signals: Dict[str, float]       # raw signal values (same shape as v3)
    weights_used: Dict[str, float]  # per-signal weights after redistribution
    buckets: Dict[str, float]       # pre-entropy bucket contributions
    city_slug: Optional[str]
    computed_at: datetime


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def compute_place_score_v4(
    *,
    place_id: str,
    name: str,
    lat: Optional[float],
    lng: Optional[float],
    has_menu: bool,
    website: Optional[str],
    updated_at: Optional[datetime],
    grubhub_url: Optional[str],
    menu_source_url: Optional[str],
    image_count: int,
    has_primary_image: bool,
    menu_item_count: int,
    hitlist_score: float = 0.0,
    creator_score: float = 0.0,
    awards_score: float = 0.0,
    blog_score: float = 0.0,
    # v4 new parameters
    creator_mention_count: int = 0,
    risk_score: float = 0.0,
    city_slug: Optional[str] = None,
) -> ScoreV4Result:
    # ------------------------------------------------------------------
    # 1. Build raw signals (same normalization as v3)
    # ------------------------------------------------------------------
    gated_creator = _apply_consensus_gate(
        _clamp(creator_score), creator_mention_count
    )

    signals: Dict[str, float] = {
        "menu_score":         _clamp(min(menu_item_count / 50.0, 1.0)),
        "image_score":        _clamp(min(image_count / 5.0, 1.0)),
        "completeness_score": _completeness(
            name=name, lat=lat, lng=lng,
            has_image=has_primary_image,
            has_menu=has_menu, website=website,
        ),
        "recency_score":      _recency(updated_at),
        "app_score":          1.0 if (grubhub_url or menu_source_url) else 0.0,
        "hitlist_score":      _clamp(hitlist_score),
        # creator_score stored as the consensus-gated value so callers see the
        # effective contribution, not the raw input.
        "creator_score":      gated_creator,
        "awards_score":       _clamp(awards_score),
        "blog_score":         _clamp(blog_score),
    }

    # ------------------------------------------------------------------
    # 2. Weight redistribution
    #
    # Authority (awards_score) and risk are kept out of the base
    # redistribution pool — same reasoning as v3:
    #   • Authority signals are additive; including them in redistribution
    #     would drain weight from well-scoring base signals.
    #   • Risk is subtractive and handled separately.
    # ------------------------------------------------------------------
    _AUTHORITY = {"awards_score"}
    # Risk has no entry in city weight profiles yet; handled separately below.

    base_signals = {k: v for k, v in signals.items() if k not in _AUTHORITY}
    weights = get_profile(city_slug)
    base_weights = _redistribute_weights(weights, base_signals)

    # weights_used: base redistribution + raw authority weights + risk placeholder
    weights_used: Dict[str, float] = {
        **base_weights,
        **{k: weights[k] for k in _AUTHORITY},
        "risk": 0.0,  # structure present; weight activates once risk data exists
    }

    # ------------------------------------------------------------------
    # 3. Compute bucket scores (pre-entropy, pre-boost)
    # ------------------------------------------------------------------
    structural_val  = compute_structural(signals, weights_used)
    authenticity_val = compute_authenticity(signals, weights_used)
    authority_val   = compute_authority(signals, weights_used)
    momentum_val    = compute_momentum(signals, weights_used)
    # risk_weight is 0.0 — no entry in city profiles yet; placeholder for future.
    risk_weight: float = 0.0
    risk_val = compute_risk(risk_score, risk_weight)

    buckets: Dict[str, float] = {
        "structural":   structural_val,
        "authenticity": authenticity_val,
        "authority":    authority_val,
        "momentum":     momentum_val,
        "risk":         risk_val,
    }

    # ------------------------------------------------------------------
    # 4. Cross-source boost (same logic as v3, max 3 %)
    # ------------------------------------------------------------------
    active_types = sum(1 for s in [
        signals["creator_score"],
        signals["awards_score"],
        signals["blog_score"],
        signals["hitlist_score"],
        signals["app_score"],
    ] if s > 0.0)

    if active_types >= 3:
        cross_source_boost = 0.03
    elif active_types == 2:
        cross_source_boost = 0.015
    else:
        cross_source_boost = 0.0

    # ------------------------------------------------------------------
    # 5. Final score assembly
    # ------------------------------------------------------------------
    score = structural_val + authenticity_val + authority_val + momentum_val
    score = min(1.0, score + cross_source_boost)
    score = _clamp(score + _uuid_entropy(place_id))
    score = max(0.0, score - risk_val)

    return ScoreV4Result(
        final_score=round(score, 6),
        signals=signals,
        weights_used=weights_used,
        buckets=buckets,
        city_slug=city_slug,
        computed_at=_utcnow(),
    )
