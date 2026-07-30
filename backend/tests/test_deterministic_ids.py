"""
Coverage for the deterministic UUID helpers used across seeding/import
scripts (app/scripts/seed_places.py, scripts/import_blog_signals.py,
scripts/targeted_enrichment.py, scripts/import_osm_candidates.py,
scripts/import_award_signals.py) to dedupe places/cities/categories by a
stable id derived from their natural key, instead of a random uuid4()
that would create a fresh row every time the same script re-runs.

This file was 0 bytes before this pass.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.models.category import category_uuid
from app.db.models.city import city_uuid
from app.db.models.place import place_uuid


def _is_valid_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
        return True
    except (ValueError, AttributeError):
        return False


class TestPlaceUuid:
    def test_returns_a_valid_uuid_string(self):
        assert _is_valid_uuid(place_uuid("Joe's Diner", "city-1"))

    def test_is_deterministic_for_the_same_inputs(self):
        a = place_uuid("Joe's Diner", "city-1")
        b = place_uuid("Joe's Diner", "city-1")
        assert a == b

    def test_is_case_and_whitespace_insensitive_on_name(self):
        a = place_uuid("Joe's Diner", "city-1")
        b = place_uuid("  JOE'S DINER  ", "city-1")
        assert a == b

    def test_differs_for_a_different_name(self):
        a = place_uuid("Joe's Diner", "city-1")
        b = place_uuid("Jane's Diner", "city-1")
        assert a != b

    def test_differs_for_a_different_city(self):
        a = place_uuid("Joe's Diner", "city-1")
        b = place_uuid("Joe's Diner", "city-2")
        assert a != b

    def test_handles_none_gracefully(self):
        # normalize() treats None as "" via `(name or "").strip()`
        assert _is_valid_uuid(place_uuid(None, None))  # type: ignore[arg-type]


class TestCityUuid:
    def test_returns_a_valid_uuid_string(self):
        assert _is_valid_uuid(city_uuid("san-francisco"))

    def test_is_deterministic_for_the_same_slug(self):
        assert city_uuid("san-francisco") == city_uuid("san-francisco")

    def test_is_case_insensitive(self):
        assert city_uuid("San-Francisco") == city_uuid("san-francisco")

    def test_differs_for_a_different_slug(self):
        assert city_uuid("san-francisco") != city_uuid("oakland")


class TestCategoryUuid:
    def test_returns_a_valid_uuid_string(self):
        assert _is_valid_uuid(category_uuid("pizza"))

    def test_is_deterministic_for_the_same_slug(self):
        assert category_uuid("pizza") == category_uuid("pizza")

    def test_is_case_insensitive(self):
        assert category_uuid("Pizza") == category_uuid("pizza")

    def test_differs_for_a_different_slug(self):
        assert category_uuid("pizza") != category_uuid("sushi")


def test_namespaces_are_isolated_across_entity_types():
    # The same raw string run through each helper must not collide —
    # they're salted with different namespace UUIDs (and category_uuid
    # additionally prefixes "category:"), so a place/city/category that
    # happen to share a slug/name never accidentally share an id.
    ids = {place_uuid("thing", "thing"), city_uuid("thing"), category_uuid("thing")}
    assert len(ids) == 3
