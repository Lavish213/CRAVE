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

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.config.settings import settings
from app.services.ingest.google_places_ingest import (
    GooglePlacesBudgetExhausted,
    GoogleQuotaExhausted,
    GooglePlacesIngest,
    _NON_RESTAURANT_TYPES,
)


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


# --------------------------------------------------------------------------
# Per-run call budget cap (Settings.google_places_max_calls_per_run) — added
# after a production audit flagged that nothing bounded how many Google
# Places API calls a single ingest run could rack up (an oversized grid or
# a bad step_km could run up real billing with no safety net). These test
# the counter/exception logic directly rather than mocking HTTP, since
# _consume_call_budget() is pure bookkeeping independent of the network call.
# --------------------------------------------------------------------------

def test_default_max_calls_per_run_comes_from_settings():
    g = GooglePlacesIngest(api_key="fake")
    assert g.max_calls_per_run == settings.google_places_max_calls_per_run


def test_explicit_max_calls_per_run_overrides_settings_default():
    g = GooglePlacesIngest(api_key="fake", max_calls_per_run=5)
    assert g.max_calls_per_run == 5


def test_consume_call_budget_raises_once_cap_is_exceeded():
    g = GooglePlacesIngest(api_key="fake", max_calls_per_run=2)
    g._consume_call_budget()
    g._consume_call_budget()
    with pytest.raises(GooglePlacesBudgetExhausted):
        g._consume_call_budget()


def test_zero_max_calls_per_run_disables_the_cap():
    g = GooglePlacesIngest(api_key="fake", max_calls_per_run=0)
    for _ in range(50):
        g._consume_call_budget()  # should never raise


def test_budget_exhausted_is_caught_by_existing_quota_exhausted_handlers():
    # scan_grid/search_nearby only special-case GoogleQuotaExhausted to abort
    # the whole run — this must stay a subclass or budget exhaustion would
    # silently fall through to the generic per-cell `except Exception` path
    # instead of stopping the run.
    assert issubclass(GooglePlacesBudgetExhausted, GoogleQuotaExhausted)
