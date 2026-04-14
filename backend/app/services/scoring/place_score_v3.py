# app/services/scoring/place_score_v3.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from app.services.scoring.city_weight_profiles import get_profile

_ENTROPY_DIV = 1_000_000_000_000


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


@dataclass(frozen=True)
class ScoreV3Result:
    final_score: float
    signals: Dict[str, float]
    weights_used: Dict[str, float]
    city_slug: Optional[str]
    computed_at: datetime


def compute_place_score_v3(
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
    # creator_score hook: ready for activation once social URL data is present.
    # Expected data format: float in [0.0, 1.0].
    # Weak signal baseline = 0.3 when place.website contains instagram.com,
    # tiktok.com, youtube.com, or linktr.ee (TikTok confidence ~0.40 per spec).
    # Wire in _fetch_signal_context() in recompute_scores_worker.py.
    creator_score: float = 0.0,
    awards_score: float = 0.0,
    # blog_score hook: ready for activation once blog/press URL data is present.
    # Expected data format: float in [0.0, 1.0].
    # Currently 0.0 — no blog/press URLs exist in the DB as of 2026-04-13.
    blog_score: float = 0.0,
    city_slug: Optional[str] = None,
) -> ScoreV3Result:
    signals: Dict[str, float] = {
        "menu_score":         _clamp(min(menu_item_count / 50.0, 1.0)),
        "image_score":        _clamp(min(image_count / 10.0, 1.0)),
        "completeness_score": _completeness(
            name=name, lat=lat, lng=lng,
            has_image=has_primary_image,
            has_menu=has_menu, website=website,
        ),
        "recency_score":      _recency(updated_at),
        "app_score":          1.0 if (grubhub_url or menu_source_url) else 0.0,
        "hitlist_score":      _clamp(hitlist_score),
        "creator_score":      _clamp(creator_score),
        "awards_score":       _clamp(awards_score),
        "blog_score":         _clamp(blog_score),
    }

    weights = get_profile(city_slug)
    weights_used = _redistribute_weights(weights, signals)
    final_score = sum(signals[k] * weights_used[k] for k in weights_used)

    # Count distinct active signal types for this place
    active_types = sum(1 for s in [
        signals["creator_score"],
        signals["awards_score"],
        signals["blog_score"],
        signals["hitlist_score"],
        signals["app_score"],
    ] if s > 0.0)

    # Multi-source confidence: slight boost for places verified by multiple sources.
    # Max boost: 3% (does not change tier, just tiebreaks within cluster).
    if active_types >= 3:
        cross_source_boost = 0.03
    elif active_types == 2:
        cross_source_boost = 0.015
    else:
        cross_source_boost = 0.0

    final_score = min(1.0, final_score + cross_source_boost)

    # Entropy tiebreak: sub-micro nudge derived from place_id to break ties deterministically
    final_score = _clamp(final_score + _uuid_entropy(place_id))

    return ScoreV3Result(
        final_score=round(final_score, 6),
        signals=signals,
        weights_used=weights_used,
        city_slug=city_slug,
        computed_at=_utcnow(),
    )
