"""
feed_ranker.py — Feed Ranking and Quality System

The single canonical place for all feed ranking decisions.
All other code hands raw candidates here and trusts the output.

─── SCORING FORMULA ──────────────────────────────────────────────────────────

  final_score = (rank_score    × 0.65)   backbone quality signal
              + (prox_score    × 0.20)   proximity (0 when no location)
              + (quality_bonus × 0.10)   establishment signals
              + (explore_boost × 0.05)   deterministic pseudo-variety

  rank_score range: [0.07, 0.50]
  final_score range (no location): ~[0.045, 0.40]
  final_score range (with location): ~[0.045, 0.65]

─── DIVERSITY RULES ──────────────────────────────────────────────────────────

  1. No 2 consecutive identical categories
  2. Max 3 of same category in any 10-item window
  3. Greedy scan: scan all remaining items for the next valid pick,
     preserving score order as much as possible

─── EXPLORATION ──────────────────────────────────────────────────────────────

  15% of places get a deterministic boost (0.01–0.03) seeded on place_id.
  Uses CRC32 — stable across requests, unique per place.
  Effect: near-tie clusters resolve differently without feeling random.

─── SATURATION PENALTY ───────────────────────────────────────────────────────

  Applied when a category dominates the candidate pool.
  Pulls over-represented categories down slightly before diversity,
  so diversity feels natural rather than mechanical.
"""
from __future__ import annotations

import math
import zlib
from collections import defaultdict
from typing import Dict, List, Optional

from app.db.models.place import Place

# ─── Constants ────────────────────────────────────────────────────────────────

_DEG_TO_KM = 111.0
_KM_TO_MILES = 0.621371

_TIER_THRESHOLDS = (
    (0.42, "crave_pick"),
    (0.32, "gem"),
    (0.22, "solid"),
)

_GENERIC_CATS = frozenset({"restaurant", "restaurants", "bar", "bars", "other", "others", ""})

# Diversity window settings
_DIVERSITY_WINDOW = 10
_MAX_SAME_IN_WINDOW = 3

# Exploration boost
_EXPLORE_PCT = 15       # 15% of places receive a boost
_EXPLORE_MIN = 0.010
_EXPLORE_MAX = 0.030

# Saturation: penalty kicks in when a category has this many candidates
_SAT_SOFT = 5
_SAT_HARD = 10
_SAT_MAX = 20

# Chain penalty: well-known national/global chains get deprioritized
# CRAVE is for local discovery — chains are findable everywhere else
_CHAIN_PENALTY = -0.06
_CHAINS = frozenset({
    "mcdonald", "mcdonalds", "mcdonald's",
    "subway",
    "starbucks",
    "taco bell",
    "burger king",
    "wendy", "wendys", "wendy's",
    "domino", "dominos", "domino's",
    "pizza hut",
    "papa john", "papa johns",
    "kfc",
    "popeyes", "popeye's",
    "chick-fil-a", "chick fil a",
    "chipotle",
    "panda express",
    "jack in the box",
    "in-n-out", "in n out",
    "five guys",
    "shake shack",
    "habit burger", "the habit",
    "wingstop",
    "raising cane", "raising cane's",
    "del taco",
    "carl's jr", "carls jr",
    "hardee",
    "sonic drive",
    "dairy queen",
    "baskin-robbins", "baskin robbins",
    "dunkin", "dunkin donuts", "dunkin'",
    "tim horton", "tim hortons",
    "panera",
    "jersey mike", "jersey mike's",
    "jimmy john", "jimmy john's",
    "quiznos",
    "firehouse subs",
    "arby",
    "white castle",
    "trader joe",  # grocery, not restaurant
    "whole foods",
    "safeway",
    "ralphs",
    "7-eleven", "7 eleven",
    "speedway",
    "circle k",
})


# ─── Public helpers ───────────────────────────────────────────────────────────

def rank_to_tier(score: float) -> str:
    """Convert rank_score → tier key. Mirrors scoring.ts getTier()."""
    for threshold, tier in _TIER_THRESHOLDS:
        if score >= threshold:
            return tier
    return "new"


def compute_distance_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Pythagorean distance approximation. Accurate within ~50 miles."""
    dlat = lat2 - lat1
    dlng = (lng2 - lng1) * math.cos(math.radians(lat1))
    km = math.sqrt(dlat ** 2 + dlng ** 2) * _DEG_TO_KM
    return round(km * _KM_TO_MILES, 2)


# ─── Internal helpers ─────────────────────────────────────────────────────────

def _primary_cat(p: Place) -> str:
    """First non-generic category name from place, lowercased. Falls back to '_other'."""
    for c in (p.categories or []):
        name = getattr(c, "name", str(c) or "").lower()
        if name and name not in _GENERIC_CATS:
            return name
    return "_other"


def _prox_score(distance_miles: float) -> float:
    """
    Proximity score ∈ [0, 1].
      0mi  → 1.000
      5mi  → 0.667
     10mi  → 0.500
     20mi  → 0.333
     50mi  → 0.167
    """
    return 1.0 / (1.0 + distance_miles / 10.0)


def _quality_bonus(p: Place) -> float:
    """
    Establishment quality signals not fully captured by rank_score alone.

    rank_score already weights images (+0.13) and website (+0.10).
    These bonuses amplify slightly for tie-breaking without dominating.

    Max bonus: 0.025 (very small — intentional)
    """
    bonus = 0.0
    # Confirmed web presence (website already in rank_score — small amplifier)
    if p.website:
        bonus += 0.010
    # Has address data (adds real-world navigation trust)
    if p.address:
        bonus += 0.005
    # Well-categorized → indicates a more established, described venue
    specific_count = sum(
        1 for c in (p.categories or [])
        if getattr(c, "name", "").lower() not in _GENERIC_CATS
    )
    if specific_count >= 2:
        bonus += 0.005
    if specific_count >= 3:
        bonus += 0.005
    return bonus


def _explore_boost(p: Place) -> float:
    """
    Deterministic pseudo-random exploration boost.

    Uses CRC32 of place_id as a stable per-place seed.
    ~15% of places receive a 0.01–0.03 boost.

    This breaks rank_score ties in a stable but varied way:
    - Same place always ranks at same position
    - But the distribution feels un-algorithmic
    - Different users see same order (consistent discovery)
    - Near-ties resolve differently than pure id-sort
    """
    try:
        crc = zlib.crc32(p.id.encode()) & 0xFFFFFFFF
    except Exception:
        return 0.0
    pct = crc % 100
    if pct >= _EXPLORE_PCT:
        return 0.0
    # pct ∈ [0, 14] → map to [EXPLORE_MIN, EXPLORE_MAX]
    t = pct / _EXPLORE_PCT
    return _EXPLORE_MIN + t * (_EXPLORE_MAX - _EXPLORE_MIN)


def _chain_penalty(p: Place) -> float:
    """
    Penalty for national/global chains.

    CRAVE is local discovery — chains are already universally known.
    Any place whose name contains a known chain marker gets -0.06,
    pushing them below local alternatives at the same quality level.
    """
    name = (p.name or "").lower()
    for chain in _CHAINS:
        if chain in name:
            return _CHAIN_PENALTY
    return 0.0


def _saturation_penalty(cat: str, cat_counts: Dict[str, int]) -> float:
    """
    Soft pre-diversity penalty when a category dominates the candidate pool.

    Reduces dominant categories' absolute scores slightly so diversity
    logic has less work to do and feels more natural.

    Penalty bands:
      5–9   candidates: -0.010
      10–19 candidates: -0.020
      20+   candidates: -0.030
    """
    count = cat_counts.get(cat, 0)
    if count < _SAT_SOFT:
        return 0.0
    if count < _SAT_HARD:
        return -0.010
    if count < _SAT_MAX:
        return -0.020
    return -0.030


def _compute_final_score(
    p: Place,
    distance_miles: Optional[float],
    cat_counts: Dict[str, int],
) -> float:
    """
    Compute final feed score for a single candidate.

    final_score = rank × W_rank + prox × W_prox + quality × 0.10 + explore × 0.05
                + saturation_penalty

    W_rank and W_prox shift based on location availability:
    - With location:    rank=0.65, prox=0.20
    - Without location: rank=0.65, prox=0.00 (proximity unused, not redistributed)
    """
    rank = p.rank_score or 0.0
    cat = _primary_cat(p)

    prox_w = 0.20 if distance_miles is not None else 0.0
    prox = _prox_score(distance_miles) if distance_miles is not None else 0.0

    quality = _quality_bonus(p)
    explore = _explore_boost(p)
    sat_pen = _saturation_penalty(cat, cat_counts)
    chain_pen = _chain_penalty(p)

    return (
        rank * 0.65
        + prox * prox_w
        + quality * 0.10
        + explore * 0.05
        + sat_pen
        + chain_pen
    )


def _diversify(places: List[Place]) -> List[Place]:
    """
    Greedy window-constrained diversity enforcement.

    Rules:
    1. No 2 consecutive identical categories
    2. Max 3 of same category in any 10-item window

    Algorithm: for each slot in output, scan remaining items (in score order)
    for the highest-scored item that satisfies constraints. When no item
    satisfies, relax and take the highest-scored remaining (prevents deadlock).

    This preserves score ordering much better than round-robin because
    high-quality items from underrepresented categories can skip past
    lower-quality items from over-represented categories.
    """
    result: List[Place] = []
    remaining = list(places)

    while remaining:
        placed = False
        last_cat = _primary_cat(result[-1]) if result else None
        window_cats = [_primary_cat(r) for r in result[-_DIVERSITY_WINDOW:]]

        for i, p in enumerate(remaining):
            cat = _primary_cat(p)
            # Constraint 1: no consecutive same category
            if cat == last_cat:
                continue
            # Constraint 2: max 3 in window
            if window_cats.count(cat) >= _MAX_SAME_IN_WINDOW:
                continue
            result.append(p)
            remaining.pop(i)
            placed = True
            break

        if not placed:
            # All remaining items violate constraints — relax and take next best
            result.append(remaining.pop(0))

    return result


# ─── Public API ───────────────────────────────────────────────────────────────

def rank_feed(
    candidates: List[Place],
    *,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    limit: int = 40,
) -> List[Place]:
    """
    Rank a candidate pool for feed display.

    Steps:
      1. Compute distance_miles for each candidate → injects as Place attribute
      2. Count category representation for saturation penalties
      3. Score each candidate (blended quality + proximity + bonus + explore)
      4. Sort by final_score DESC (stable: place_id as tiebreaker)
      5. Apply diversity enforcement (greedy window-constrained)
      6. Return top `limit`

    Args:
      candidates: raw Place objects from SQL retrieval layer
      lat, lng: user location (optional — omit for global/city feed)
      limit: max results to return

    Side effect:
      Sets `distance_miles` attribute on each returned Place so
      PlaceOut._inject_category serializes it without extra queries.
    """
    if not candidates:
        return []

    has_location = lat is not None and lng is not None

    # ── Step 1: Compute distances ──────────────────────────────────────────────
    for p in candidates:
        dist: Optional[float] = None
        if has_location and p.lat is not None and p.lng is not None:
            dist = compute_distance_miles(lat, lng, p.lat, p.lng)  # type: ignore[arg-type]
        p.distance_miles = dist  # type: ignore[attr-defined]

    # ── Step 2: Category saturation counts ────────────────────────────────────
    cat_counts: Dict[str, int] = defaultdict(int)
    for p in candidates:
        cat_counts[_primary_cat(p)] += 1

    # ── Step 3: Score all candidates ──────────────────────────────────────────
    scored: List[tuple[float, str, Place]] = []
    for p in candidates:
        score = _compute_final_score(p, p.distance_miles, cat_counts)
        # Include place_id as tiebreaker for stable sort at equal scores
        scored.append((score, p.id, p))

    # ── Step 4: Sort by final_score DESC (id ASC for ties) ────────────────────
    scored.sort(key=lambda x: (-x[0], x[1]))
    ranked = [p for _, _, p in scored]

    # ── Step 5: Diversity enforcement ─────────────────────────────────────────
    diversified = _diversify(ranked)

    # ── Step 6: Trim to limit ─────────────────────────────────────────────────
    return diversified[:limit]
