"""
Regression coverage for app.services.query.feed_mixer.mix_feed.

Found by actually running the app against seeded data: a city where
places don't have a resolved category (very common — see
discovery_service.ingest_candidate_v2's category resolution, and this
app's own OSM ingestion job which frequently can't map an OSM category
hint to a known Category) had only its first two places ever show up in
the feed, no matter how many active places existed. Every place after
that silently vanished.

Root cause: the diversity guard compared category keys with plain `==`.
None == None is True in Python, so two consecutive uncategorized places
counted as "same category", the streak counter passed the >2 diversity
limit, and — because the streak-reset branch only fires when the
category actually changes — a category of None never resets the streak
once it starts. Every later place, categorized or not, got silently
dropped.

Important: the diversity-guard/streak logic only runs at all when BOTH
stable_places and discovery_places are non-empty (mix_feed short-circuits
to a plain slice otherwise — see the `if not discovery_places` /
`if not stable_places` branches). Every test below that means to exercise
the guard passes a real, non-empty discovery_places list, and — for the
"a real repeated category is still limited" cases — one that doesn't
overlap with stable_places' ids. Overlapping discovery entries give a
skipped place a second chance to reappear later in the discovery pass,
which is a real (and fine) behavior of the mixer, but it would silently
give those specific tests a false pass regardless of whether the guard
logic being tested was actually correct.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.query.feed_mixer import mix_feed


class FakePlace:
    """Minimal stand-in for app.db.models.place.Place — mix_feed only
    ever touches .id and .categories (via feed_mixer._category_key), so a
    real ORM instance (which needs a DB session + city) isn't needed."""

    def __init__(self, place_id: str, category_id: Optional[str] = None):
        self.id = place_id
        self.categories = [FakeCategory(category_id)] if category_id else []


class FakeCategory:
    def __init__(self, category_id: str):
        self.id = category_id


def _ids(places: List[FakePlace]) -> List[str]:
    return [p.id for p in places]


def test_uncategorized_places_are_not_dropped_after_two():
    stable = [FakePlace(f"p{i}") for i in range(6)]  # no category on any of them
    discovery = [FakePlace(f"d{i}") for i in range(3)]  # also uncategorized

    result = mix_feed(stable_places=stable, discovery_places=discovery, limit=50)

    assert set(_ids(result)) == {f"p{i}" for i in range(6)} | {f"d{i}" for i in range(3)}


def test_three_consecutive_same_real_category_are_still_diversity_limited():
    stable = [
        FakePlace("p0", "pizza"),
        FakePlace("p1", "pizza"),
        FakePlace("p2", "pizza"),  # 3rd consecutive real "pizza" — should be skipped
        FakePlace("p3", "sushi"),
    ]
    # Non-overlapping with stable, so a skipped place can't reappear via
    # the discovery pass (see module docstring).
    discovery = [FakePlace("d0", "mexican"), FakePlace("d1", "thai")]

    result = mix_feed(stable_places=stable, discovery_places=discovery, limit=50)

    assert "p2" not in _ids(result)
    assert set(_ids(result)) == {"p0", "p1", "p3", "d0", "d1"}


def test_a_real_category_streak_resets_after_a_different_category():
    stable = [
        FakePlace("p0", "pizza"),
        FakePlace("p1", "pizza"),
        FakePlace("p2", "sushi"),
        FakePlace("p3", "pizza"),
        FakePlace("p4", "pizza"),
    ]
    discovery = [FakePlace("d0", "mexican")]

    result = mix_feed(stable_places=stable, discovery_places=discovery, limit=50)

    # sushi in the middle resets the streak, so both later pizzas count as
    # a fresh streak of their own and are kept — none of the stable places
    # should be missing.
    assert {"p0", "p1", "p2", "p3", "p4"} <= set(_ids(result))


def test_returns_stable_only_when_discovery_is_empty():
    places = [FakePlace(f"p{i}") for i in range(3)]
    assert _ids(mix_feed(stable_places=places, discovery_places=[], limit=50)) == ["p0", "p1", "p2"]


def test_returns_discovery_only_when_stable_is_empty():
    places = [FakePlace(f"p{i}") for i in range(3)]
    assert _ids(mix_feed(stable_places=[], discovery_places=places, limit=50)) == ["p0", "p1", "p2"]


def test_returns_empty_for_no_inputs():
    assert mix_feed(stable_places=[], discovery_places=[], limit=50) == []


def test_deduplicates_places_present_in_both_stable_and_discovery():
    shared = FakePlace("shared")
    stable = [shared, FakePlace("s1")]
    discovery = [shared, FakePlace("d1")]

    result = mix_feed(stable_places=stable, discovery_places=discovery, limit=50)

    assert _ids(result).count("shared") == 1


def test_respects_the_limit():
    places = [FakePlace(f"p{i}") for i in range(10)]
    result = mix_feed(stable_places=places, discovery_places=[], limit=3)
    assert len(result) == 3
