"""
Regression coverage for app.services.ingest.google_places_ingest — real
grocery stores/dollar stores/gas stations were showing up in the feed
alongside restaurants ("Dollar General Market", "Super King" both
promoted as if they were places to eat). Root cause: SEARCH_TYPES
included Google's "food" type, which Google applies to many venues that
merely sell food/drink items, not just restaurants — and nothing
rejected a result based on its actual Google `types`.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.ingest.google_places_ingest import GooglePlacesIngest, _NON_RESTAURANT_TYPES


def _place(name, types, **overrides):
    base = {
        "name": name,
        "place_id": f"pid-{name}",
        "geometry": {"location": {"lat": 37.7749, "lng": -122.4194}},
        "types": types,
    }
    base.update(overrides)
    return base


def test_food_is_no_longer_in_search_types():
    # "food" is Google's broadest catch-all type and the direct cause of
    # this bug — asserting it's gone keeps a future edit from silently
    # reintroducing it.
    assert "food" not in GooglePlacesIngest.SEARCH_TYPES


def test_grocery_store_is_rejected():
    g = GooglePlacesIngest(api_key="fake")
    result = g._convert_place(_place(
        "Dollar General Market",
        ["grocery_or_supermarket", "food", "point_of_interest", "establishment"],
    ))
    assert result is None


def test_supermarket_is_rejected():
    g = GooglePlacesIngest(api_key="fake")
    result = g._convert_place(_place(
        "Super King",
        ["supermarket", "food", "store", "point_of_interest"],
    ))
    assert result is None


def test_gas_station_is_rejected():
    g = GooglePlacesIngest(api_key="fake")
    result = g._convert_place(_place(
        "Shell Station",
        ["gas_station", "convenience_store", "point_of_interest"],
    ))
    assert result is None


def test_real_restaurant_is_kept():
    g = GooglePlacesIngest(api_key="fake")
    result = g._convert_place(_place(
        "Genova Bakery",
        ["bakery", "cafe", "food", "point_of_interest", "establishment"],
    ))
    assert result is not None
    assert result["name"] == "Genova Bakery"
    assert result["category_hint"] == "bakery"


def test_real_restaurant_with_no_specific_subtype_is_still_kept():
    # Falls through _TYPE_TO_HINT to the generic-type fallback in
    # _best_type_hint — should still be created (just without a specific
    # category hint), NOT rejected. Only actual non-restaurant types
    # should cause rejection.
    g = GooglePlacesIngest(api_key="fake")
    result = g._convert_place(_place(
        "Generic Eatery",
        ["restaurant", "food", "point_of_interest"],
    ))
    assert result is not None


def test_non_restaurant_types_set_has_no_overlap_with_real_food_hints():
    # Sanity check: the exclusion list and the legitimate food-type
    # mapping must never share a key, or a real restaurant type could
    # get silently rejected by a future edit to either set.
    from app.services.ingest.google_places_ingest import _TYPE_TO_HINT
    assert not _NON_RESTAURANT_TYPES.intersection(_TYPE_TO_HINT.keys())
