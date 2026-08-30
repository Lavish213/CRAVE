"""
Coverage for app.services.entity.entity_matcher — specifically the brand-
alias wiring added during a full-app audit. brand_aliases.resolve_brand_alias
existed as dead code (never imported anywhere in app/) even though
entity_match() is the live dedup path used by promote_service_v2. Two
candidates for the same real chain location with genuinely different-
looking names ("KFC" vs "Kentucky Fried Chicken") are NOT textually similar
at all, so the fuzzy SequenceMatcher comparison in dedupe_rules.names_match
scored them well below FUZZY_THRESHOLD and they were never recognized as
the same place by name alone.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.entity.entity_matcher import entity_match


def _candidate(name, address=None, lat=None, lng=None, website=None):
    return {
        "name": name,
        "address": address,
        "lat": lat,
        "lng": lng,
        "website": website,
    }


def test_kfc_vs_kentucky_fried_chicken_matches_via_brand_alias():
    a = _candidate("KFC", address="123 Main St, Oakland, CA")
    b = _candidate("Kentucky Fried Chicken", address="123 Main St, Oakland, CA")
    assert entity_match(a, b) is True


def test_burgerking_vs_burger_king_matches_via_brand_alias():
    a = _candidate("BurgerKing", address="500 Elm St, Fresno, CA")
    b = _candidate("Burger King", address="500 Elm St, Fresno, CA")
    assert entity_match(a, b) is True


def test_different_brands_at_the_same_address_do_not_match():
    # Same strong address signal, but the names are neither fuzzy-similar
    # nor known aliases of each other — must not match.
    a = _candidate("KFC", address="123 Main St, Oakland, CA")
    b = _candidate("Taco Bell", address="123 Main St, Oakland, CA")
    assert entity_match(a, b) is False


def test_brand_alias_match_still_requires_a_strong_signal_or_spatial_proximity():
    # Name-only match (even via brand alias) is not enough on its own —
    # entity_match requires address match or spatial proximity too.
    a = _candidate("KFC", address="123 Main St, Oakland, CA")
    b = _candidate("Kentucky Fried Chicken", address="999 Far Away Rd, Reno, NV")
    assert entity_match(a, b) is False


def test_identical_unbranded_names_at_the_same_address_still_match():
    # Regression: ordinary exact-name matching (not involving brand
    # aliases at all) must keep working exactly as before.
    a = _candidate("Horn Barbecue", address="2534 Mandela Pkwy, Oakland, CA")
    b = _candidate("Horn Barbecue", address="2534 Mandela Pkwy, Oakland, CA")
    assert entity_match(a, b) is True


def test_distinct_branches_are_not_merged_by_shared_brand_website():
    first = _candidate(
        "North Beach Sandwicheez",
        address="308 Jackson St #5, Oakland, CA",
        lat=37.7946,
        lng=-122.2694,
        website="https://www.sandwicheez.com/",
    )
    second = _candidate(
        "North Beach Sandwicheez",
        address="300 Lakeside Dr #122, Oakland, CA",
        lat=37.8086,
        lng=-122.2646,
        website="https://www.sandwicheez.com/",
    )

    assert entity_match(first, second) is False
