"""
Coverage for app.services.decision_session.decision_session_builder --
the Decision Session's best_fit/safe_bet/wildcard selection logic. See
docs/decision_session_spec.md.

Uses plain fake Place-like objects (same precedent as
test_feed_mixer.py's FakePlace) rather than real ORM instances --
build_decision_session() and the feed_ranker functions it calls only
ever touch .id, .categories, .rank_score, .lat, .lng, .website,
.address, so a DB session isn't needed for this logic.
"""
from __future__ import annotations

from typing import List, Optional

from app.services.decision_session.decision_session_builder import build_decision_session
from app.services.feed.feed_ranker import explore_boost


class FakeCategory:
    def __init__(self, name: str):
        self.name = name


class FakePlace:
    def __init__(
        self,
        place_id: str,
        *,
        rank_score: float = 0.30,
        category: Optional[str] = None,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
        website: Optional[str] = None,
        address: Optional[str] = None,
    ):
        self.id = place_id
        self.name = f"Fake Place {place_id}"
        self.rank_score = rank_score
        self.categories = [FakeCategory(category)] if category else []
        self.lat = lat
        self.lng = lng
        self.website = website
        self.address = address


def _explore_boosted_id(prefix: str, category: str, rank_score: float = 0.20) -> FakePlace:
    """Finds a place_id (by brute-force suffix search) that actually
    receives feed_ranker's deterministic explore boost, so wildcard
    tests don't depend on getting lucky with a hardcoded id."""
    for i in range(200):
        candidate = FakePlace(f"{prefix}{i}", rank_score=rank_score, category=category)
        if explore_boost(candidate) > 0.0:
            return candidate
    raise AssertionError("could not find an explore-boosted id in 200 tries")


def test_empty_candidates_returns_no_cards():
    assert build_decision_session([], rank_percentiles={}) == []


def test_best_fit_is_always_the_top_ranked_candidate():
    places = [
        FakePlace("low", rank_score=0.10, category="pizza"),
        FakePlace("high", rank_score=0.45, category="sushi"),
        FakePlace("mid", rank_score=0.25, category="tacos"),
    ]
    cards = build_decision_session(places, rank_percentiles={})
    assert cards[0].role == "best_fit"
    assert cards[0].place.id == "high"
    assert cards[0].reason_codes == ["top_ranked_in_area"]


def test_safe_bet_requires_high_percentile_and_a_different_category_than_best_fit():
    places = [
        FakePlace("best", rank_score=0.45, category="sushi"),
        # Same category as best_fit and high percentile -- must be
        # skipped for safe_bet (category-distinctness requirement).
        FakePlace("same_cat_high_pct", rank_score=0.40, category="sushi"),
        # Different category, high percentile -- this is the real safe_bet.
        FakePlace("safe", rank_score=0.35, category="tacos"),
        # Different category but percentile below the 0.80 bar -- must
        # never qualify no matter how little else is on offer.
        FakePlace("low_pct", rank_score=0.30, category="pizza"),
    ]
    percentiles = {
        "best": 0.99,
        "same_cat_high_pct": 0.95,
        "safe": 0.85,
        "low_pct": 0.50,
    }
    cards = build_decision_session(places, rank_percentiles=percentiles)
    roles = {c.role: c for c in cards}
    assert "safe_bet" in roles
    assert roles["safe_bet"].place.id == "safe"


def test_no_safe_bet_card_when_nothing_clears_the_percentile_bar():
    places = [
        FakePlace("best", rank_score=0.45, category="sushi"),
        FakePlace("mediocre", rank_score=0.30, category="tacos"),
    ]
    percentiles = {"best": 0.99, "mediocre": 0.60}
    cards = build_decision_session(places, rank_percentiles=percentiles)
    roles = {c.role for c in cards}
    assert "safe_bet" not in roles


def test_wildcard_is_drawn_from_the_explore_boosted_pool_only():
    best_fit = FakePlace("plain_best", rank_score=0.45, category="sushi")
    wildcard = _explore_boosted_id("wc", category="korean", rank_score=0.15)

    cards = build_decision_session([best_fit, wildcard], rank_percentiles={})
    roles = {c.role: c for c in cards}
    assert "wildcard" in roles
    assert roles["wildcard"].place.id == wildcard.id
    assert roles["wildcard"].reason_codes[0] == "underrated_pick"


def test_a_single_candidate_yields_only_a_best_fit_card_not_a_padded_three():
    cards = build_decision_session([FakePlace("only", rank_score=0.30)], rank_percentiles={})
    assert len(cards) == 1
    assert cards[0].role == "best_fit"


def test_no_card_is_ever_the_same_place_twice():
    wildcard = _explore_boosted_id("dup", category="sushi", rank_score=0.44)
    # Only one real candidate at all -- best_fit claims it, so neither
    # safe_bet nor wildcard may reuse the same place.
    cards = build_decision_session([wildcard], rank_percentiles={wildcard.id: 0.99})
    assert len(cards) == 1
    ids = [c.place.id for c in cards]
    assert len(ids) == len(set(ids))
