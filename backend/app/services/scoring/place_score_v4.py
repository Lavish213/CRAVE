# app/services/scoring/place_score_v4.py
#
# V4 scoring model — cultural discovery architecture.
# 5-bucket: structural (capped) + authenticity (gated + multiplied) +
#           authority (additive) + momentum + hidden_gem - risk
#
# DO NOT import place_score_v3; helpers are copied here intentionally.
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

_ENTROPY_DIV = 1_000_000_000_000

# ---------------------------------------------------------------------------
# Bucket weights — defined at module level for clarity and testability
# ---------------------------------------------------------------------------

# Structural bucket (individual signal weights; bucket is capped at _STRUCTURAL_CAP)
# Deliberately under-weighted so that cultural signals can compete and win.
_W_IMAGE        = 0.10
_W_COMPLETENESS = 0.10
_W_MENU         = 0.14
_W_APP          = 0.10
_W_RECENCY      = 0.06
_STRUCTURAL_CAP = 0.28  # hard cap — prevents data-rich chains from dominating

# Authenticity bucket (cultural signals; subject to gating + multiplier)
# Combined ceiling: 0.34 * 1.35 multiplier, capped at base+0.08 = ~0.40+
_W_BLOG    = 0.12
_W_CREATOR = 0.10
_W_HITLIST = 0.12

# Authority bucket (awards — additive, outside redistribution)
_W_AWARDS = 0.08

# Risk (subtracted after all positive contributions)
_RISK_WEIGHT = 0.08

# Hidden gem boost range
_HIDDEN_GEM_MIN  = 0.05
_HIDDEN_GEM_MAX  = 0.10


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


# ---------------------------------------------------------------------------
# Signal gating — thresholds differ by signal type
# ---------------------------------------------------------------------------

def _gate_creator(score: float, mention_count: int) -> float:
    """
    Gate creator_score by distinct-provider mention count.

    Social posts are cheap — require consensus before full weight.
    < 2 mentions → weak (0.25x)  — possible discovery, no ranking confidence
    2–3 mentions → medium (0.5x) — building signal, partial credit
    ≥ 4 mentions → full (1.0x)   — clear consensus, full contribution
    """
    if mention_count >= 4:
        return score
    if mention_count >= 2:
        return score * 0.5
    return score * 0.25


def _gate_blog(score: float, mention_count: int) -> float:
    """
    Gate blog_score by distinct editorial source count.

    Editorial curation costs more than social posts, so thresholds mirror creator.
    < 2 sources → weak (0.25x)
    2–3 sources → medium (0.5x)
    ≥ 4 sources → full (1.0x)
    """
    if mention_count >= 4:
        return score
    if mention_count >= 2:
        return score * 0.5
    return score * 0.25


def _gate_hitlist(score: float, save_count: int) -> float:
    """
    Gate hitlist_score by raw save count (not normalized score).

    < 5 saves  → weak (0.25x)  — could be personal list noise
    5–19 saves → medium (0.5x) — community is noticing
    ≥ 20 saves → full (1.0x)   — clear community endorsement
    """
    if save_count >= 20:
        return score
    if save_count >= 5:
        return score * 0.5
    return score * 0.25


# ---------------------------------------------------------------------------
# 1. Structural bucket
# ---------------------------------------------------------------------------

def compute_structural(
    *,
    image_score: float,
    completeness_score: float,
    menu_score: float,
    app_score: float,
    recency_score: float,
) -> float:
    """
    Data-quality signals: how well-described is this place?
    Hard-capped at _STRUCTURAL_CAP to prevent data richness from dominating ranking.
    """
    raw = (
        image_score        * _W_IMAGE        +
        completeness_score * _W_COMPLETENESS +
        menu_score         * _W_MENU         +
        app_score          * _W_APP          +
        recency_score      * _W_RECENCY
    )
    return min(raw, _STRUCTURAL_CAP)


# ---------------------------------------------------------------------------
# 2. Authenticity bucket
# ---------------------------------------------------------------------------

def compute_authenticity(
    *,
    blog_score: float,
    blog_mention_count: int,
    creator_score: float,
    creator_mention_count: int,
    hitlist_score: float,
    hitlist_count: int,
) -> float:
    """
    Cultural + community signals, gated by consensus then amplified if multiple
    independent signal types align.
    """
    gated_blog    = _gate_blog(blog_score, blog_mention_count)
    gated_creator = _gate_creator(creator_score, creator_mention_count)
    gated_hitlist = _gate_hitlist(hitlist_score, hitlist_count)

    base = (
        gated_blog    * _W_BLOG    +
        gated_creator * _W_CREATOR +
        gated_hitlist * _W_HITLIST
    )

    # Cross-source authenticity multiplier — independent cultural signals
    # validate each other. Cap: multiplier cannot add more than +0.08 absolute
    # (avoids runaway scores when base authenticity is already high).
    blog_active    = gated_blog    > 0.0
    creator_active = gated_creator > 0.0
    hitlist_active = gated_hitlist > 0.0

    active = sum([blog_active, creator_active, hitlist_active])
    if active >= 3:
        multiplier = 1.35
    elif active == 2:
        multiplier = 1.15
    else:
        multiplier = 1.0

    amplified = base * multiplier
    # Cap the boost portion at +0.08 to prevent excessive amplification
    return min(amplified, base + 0.08)


# ---------------------------------------------------------------------------
# 3. Authority bucket
# ---------------------------------------------------------------------------

def compute_authority(*, awards_score: float) -> float:
    """
    Third-party validation: awards are additive on top of cultural signals.
    NOT part of redistribution — awards validate, they don't replace data quality.
    """
    return _clamp(awards_score) * _W_AWARDS


# ---------------------------------------------------------------------------
# 4. Momentum bucket
# ---------------------------------------------------------------------------

def compute_momentum(*, recency_score: float) -> float:
    """
    Recency signal is already inside structural. Momentum is a separate
    freshness amplifier — currently a pass-through placeholder for future
    velocity signals (trending, review velocity, etc.).
    Kept at 0 weight to avoid double-counting with structural recency.
    """
    # Recency is included in structural bucket.
    # This bucket is reserved for velocity signals (not yet wired).
    return 0.0


# ---------------------------------------------------------------------------
# 5. Risk bucket
# ---------------------------------------------------------------------------

def compute_risk(*, risk_score: float) -> float:
    """
    Penalty for risk signals (editorial warnings, negative mentions).
    Subtracted AFTER all positive contributions. Capped to never nuke a place
    completely — even a high-risk place retains its core score minus max 8%.
    """
    return _clamp(risk_score) * _RISK_WEIGHT


# ---------------------------------------------------------------------------
# 6. Hidden gem boost
# ---------------------------------------------------------------------------

def compute_hidden_gem_boost(
    *,
    structural_capped: float,
    authenticity_val: float,
    awards_score: float,
    risk_score: float,
) -> float:
    """
    Surface culturally-validated places that lack structural footprint.

    Condition: low data richness (structural < 0.30) + strong cultural signal
    (authenticity > 0.25) + not establishment-tier (awards < 0.50) + low risk.

    Boost scales with authenticity strength above threshold: +0.05 to +0.10.
    This is the mechanism that puts a cash-only TikTok gem above a well-catalogued chain.
    """
    if structural_capped >= 0.25:
        return 0.0  # not a gem — has enough structural presence
    if authenticity_val <= 0.15:
        return 0.0  # not culturally validated
    if awards_score >= 0.50:
        return 0.0  # establishment-tier, not a hidden gem
    if risk_score >= 0.50:
        return 0.0  # flagged — don't boost

    # Scale with how far above the authenticity threshold
    gap = authenticity_val - 0.25
    boost = _HIDDEN_GEM_MIN + gap * 0.25
    return min(_HIDDEN_GEM_MAX, boost)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ScoreV4Result:
    final_score: float
    signals: Dict[str, float]        # raw signal values
    weights_used: Dict[str, float]   # per-signal weights
    buckets: Dict[str, float]        # per-bucket contributions (pre-entropy)
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
    hitlist_count: int = 0,
    creator_score: float = 0.0,
    creator_mention_count: int = 0,
    awards_score: float = 0.0,
    blog_score: float = 0.0,
    blog_mention_count: int = 0,
    risk_score: float = 0.0,
    city_slug: Optional[str] = None,
) -> ScoreV4Result:
    # ------------------------------------------------------------------
    # 1. Normalize raw inputs into [0, 1] signals
    # ------------------------------------------------------------------
    image_score        = _clamp(min(image_count / 5.0, 1.0))
    menu_score         = _clamp(min(menu_item_count / 50.0, 1.0))
    completeness_score = _completeness(
        name=name, lat=lat, lng=lng,
        has_image=has_primary_image,
        has_menu=has_menu, website=website,
    )
    recency_score = _recency(updated_at)
    app_score     = 1.0 if (grubhub_url or menu_source_url) else 0.0

    signals: Dict[str, float] = {
        "menu_score":         menu_score,
        "image_score":        image_score,
        "completeness_score": completeness_score,
        "recency_score":      recency_score,
        "app_score":          app_score,
        "hitlist_score":      _clamp(hitlist_score),
        "creator_score":      _clamp(creator_score),
        "awards_score":       _clamp(awards_score),
        "blog_score":         _clamp(blog_score),
    }

    # ------------------------------------------------------------------
    # 2. Structural bucket — capped at 0.35
    # ------------------------------------------------------------------
    structural_capped = compute_structural(
        image_score=image_score,
        completeness_score=completeness_score,
        menu_score=menu_score,
        app_score=app_score,
        recency_score=recency_score,
    )

    # ------------------------------------------------------------------
    # 3. Authenticity bucket — gated + multiplied
    # ------------------------------------------------------------------
    authenticity_val = compute_authenticity(
        blog_score=signals["blog_score"],
        blog_mention_count=blog_mention_count,
        creator_score=signals["creator_score"],
        creator_mention_count=creator_mention_count,
        hitlist_score=signals["hitlist_score"],
        hitlist_count=hitlist_count,
    )

    # ------------------------------------------------------------------
    # 4. Authority bucket — additive, not redistributed
    # ------------------------------------------------------------------
    authority_val = compute_authority(awards_score=signals["awards_score"])

    # ------------------------------------------------------------------
    # 5. Momentum bucket — reserved for velocity signals
    # ------------------------------------------------------------------
    momentum_val = compute_momentum(recency_score=recency_score)

    # ------------------------------------------------------------------
    # 6. Risk penalty
    # ------------------------------------------------------------------
    risk_val = compute_risk(risk_score=risk_score)

    # ------------------------------------------------------------------
    # 7. Hidden gem boost
    # ------------------------------------------------------------------
    hidden_gem_boost = compute_hidden_gem_boost(
        structural_capped=structural_capped,
        authenticity_val=authenticity_val,
        awards_score=signals["awards_score"],
        risk_score=risk_score,
    )

    buckets: Dict[str, float] = {
        "structural":   structural_capped,
        "authenticity": authenticity_val,
        "authority":    authority_val,
        "momentum":     momentum_val,
        "risk":         risk_val,
        "hidden_gem":   hidden_gem_boost,
    }

    # ------------------------------------------------------------------
    # 8. Final score assembly
    #
    # structural_capped + authenticity + authority + momentum - risk + hidden_gem
    # Add uuid entropy for tie-breaking. Clamp to [0, 1].
    # ------------------------------------------------------------------
    score = (
        structural_capped
        + authenticity_val
        + authority_val
        + momentum_val
        + hidden_gem_boost
    )
    score = _clamp(score + _uuid_entropy(place_id))
    score = max(0.0, score - risk_val)

    weights_used: Dict[str, float] = {
        "image_score":        _W_IMAGE,
        "completeness_score": _W_COMPLETENESS,
        "menu_score":         _W_MENU,
        "app_score":          _W_APP,
        "recency_score":      _W_RECENCY,
        "blog_score":         _W_BLOG,
        "creator_score":      _W_CREATOR,
        "hitlist_score":      _W_HITLIST,
        "awards_score":       _W_AWARDS,
        "risk":               _RISK_WEIGHT,
        "structural_cap":     _STRUCTURAL_CAP,
    }

    return ScoreV4Result(
        final_score=round(score, 6),
        signals=signals,
        weights_used=weights_used,
        buckets=buckets,
        city_slug=city_slug,
        computed_at=_utcnow(),
    )
