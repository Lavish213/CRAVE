"""
decision_session_builder.py -- Decision Session, Phase 1 narrow slice.

Selects up to 3 cards (best_fit / safe_bet / wildcard) out of the exact
same scored, diversified candidate list feed_ranker.rank_feed() already
produces for Feed -- no separate ranking model, no LLM, no hard-
constraint intent parsing yet. See docs/decision_session_spec.md for the
full contract and rationale.

Deliberately conservative: a role is only assigned when a real
candidate qualifies for it. Never pads to 3 with a lower-quality filler
-- an honest 1-card or 2-card response is correct when the catalog for
that area is thin; a fabricated "safe bet" that doesn't actually meet
the bar would be exactly the kind of unearned-confidence recommendation
the product doctrine explicitly warns against.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from app.db.models.place import Place
from app.db.models.recommendation_event import (
    DECISION_ROLE_BEST_FIT,
    DECISION_ROLE_SAFE_BET,
    DECISION_ROLE_WILDCARD,
)
from app.services.feed.feed_ranker import explore_boost, primary_category, rank_feed

# Matches places.py::_rank_to_tier's "gem"/"crave_pick" boundary -- a
# safe_bet must be at least as good as what the app itself already
# calls a strong tier, not a bespoke threshold invented just for this
# feature.
_SAFE_BET_MIN_PERCENTILE = 0.80


@dataclass(frozen=True)
class DecisionCard:
    place: Place
    role: str
    reason_codes: List[str]


def _rank_percentile_of(place: Place, rank_percentiles: dict) -> Optional[float]:
    return rank_percentiles.get(place.id)


def build_decision_session(
    candidates: List[Place],
    *,
    rank_percentiles: dict,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
) -> List[DecisionCard]:
    """
    Args:
      candidates: raw Place objects from the same Layer-1 retrieval
        /places uses (list_places_near / get_feed_places / query_list_places).
      rank_percentiles: place_id -> rank_percentile, from
        rank_percentile_query.get_rank_percentiles() -- passed in rather
        than queried here so this stays a pure function over its inputs,
        matching feed_ranker.rank_feed()'s own shape.
      lat, lng: optional user location, forwarded to rank_feed() so
        distance factors into the same ranking Feed itself would use.

    Returns 0-3 DecisionCards. Never raises on a thin candidate pool --
    returns fewer cards instead.
    """
    if not candidates:
        return []

    ranked = rank_feed(candidates, lat=lat, lng=lng, limit=len(candidates))
    if not ranked:
        return []

    cards: List[DecisionCard] = []
    used_ids: set = set()
    used_categories: set = set()

    # -- Best fit: rank #1, no conditions beyond "a candidate exists" --
    best_fit = ranked[0]
    cards.append(
        DecisionCard(
            place=best_fit,
            role=DECISION_ROLE_BEST_FIT,
            reason_codes=["top_ranked_in_area"],
        )
    )
    used_ids.add(best_fit.id)
    used_categories.add(primary_category(best_fit))

    # -- Safe bet: highest-ranked remaining candidate with a strong
    # percentile, from a category the pick above hasn't already used --
    for p in ranked:
        if p.id in used_ids:
            continue
        percentile = _rank_percentile_of(p, rank_percentiles)
        if percentile is None or percentile < _SAFE_BET_MIN_PERCENTILE:
            continue
        if primary_category(p) in used_categories:
            continue
        reasons = ["high_percentile"]
        if getattr(p, "distance_miles", None) is not None and p.distance_miles <= 5:
            reasons.append("close_by")
        cards.append(DecisionCard(place=p, role=DECISION_ROLE_SAFE_BET, reason_codes=reasons))
        used_ids.add(p.id)
        used_categories.add(primary_category(p))
        break

    # -- Wildcard: highest-ranked remaining candidate that got Feed's own
    # deterministic explore-boost, from a still-unused category --
    for p in ranked:
        if p.id in used_ids:
            continue
        if explore_boost(p) <= 0.0:
            continue
        if primary_category(p) in used_categories:
            continue
        reasons = ["underrated_pick"]
        if used_categories:
            reasons.append("different_cuisine")
        cards.append(DecisionCard(place=p, role=DECISION_ROLE_WILDCARD, reason_codes=reasons))
        used_ids.add(p.id)
        used_categories.add(primary_category(p))
        break

    return cards
