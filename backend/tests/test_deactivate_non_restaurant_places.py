"""
Coverage for scripts/deactivate_non_restaurant_places.py — specifically
the bug found running it for real against production: a place resolved
from more than one DiscoveryCandidate (the same real place discovered via
multiple sources, deduplicated to one Place, each candidate keeping its
own resolved_place_id) crashed the original `.one_or_none()` query with
MultipleResultsFound. Nothing was ever written when this happened — the
crash was inside the read-only candidate-finding step, before the
--apply-gated commit — but the script should handle this case at all
rather than blow up on it.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.discovery_candidate import DiscoveryCandidate
from scripts.deactivate_non_restaurant_places import _find_candidates_to_deactivate


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def city(db):
    suffix = uuid.uuid4().hex[:8]
    c = City(slug=f"deactivate-test-{suffix}", name=f"Deactivate Test City {suffix}")
    db.add(c)
    db.commit()

    yield c

    db.query(DiscoveryCandidate).filter(DiscoveryCandidate.city_id == c.id).delete()
    db.query(Place).filter(Place.city_id == c.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_place(db, city, name="Test Place"):
    p = Place(name=name, city_id=city.id, is_active=True)
    db.add(p)
    db.commit()
    return p


def _make_candidate(db, city, place, types=None):
    c = DiscoveryCandidate(
        name=place.name,
        city_id=city.id,
        resolved_place_id=place.id,
        raw_payload={"types": types} if types is not None else None,
    )
    db.add(c)
    db.commit()
    return c


def test_place_with_a_single_non_restaurant_candidate_is_flagged(db, city):
    place = _make_place(db, city, "Rite Aid")
    _make_candidate(db, city, place, types=["pharmacy", "point_of_interest"])

    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id in flagged_ids


def test_place_with_multiple_resolved_candidates_does_not_crash(db, city):
    # The exact production bug: two DiscoveryCandidate rows resolving to
    # the same place used to raise MultipleResultsFound from .one_or_none().
    place = _make_place(db, city, "Trader Joe's Annex")
    _make_candidate(db, city, place, types=["point_of_interest"])
    _make_candidate(db, city, place, types=["grocery_or_supermarket"])

    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    # Flagged via the non-restaurant type on the SECOND candidate — proves
    # the fix checks all resolved candidates, not just an arbitrary one.
    assert place.id in flagged_ids


def test_place_with_multiple_candidates_none_non_restaurant_is_not_flagged(db, city):
    place = _make_place(db, city, "Some Actual Restaurant")
    _make_candidate(db, city, place, types=["restaurant", "food"])
    _make_candidate(db, city, place, types=["point_of_interest", "establishment"])

    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_place_matching_known_chain_name_is_flagged_without_needing_a_candidate(db, city):
    place = _make_place(db, city, "CVS Pharmacy #4021")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id in flagged_ids


def test_ordinary_restaurant_with_no_candidate_is_not_flagged(db, city):
    place = _make_place(db, city, "Horn Barbecue")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_pizzeria_with_liquor_store_type_is_not_flagged(db, city):
    # Real false positive found running this script for real: pizza places
    # holding a beer/wine license get `liquor_store` in their Google types
    # alongside `restaurant` and were getting swept up as junk.
    place = _make_place(db, city, "Curry Pizza House")
    _make_candidate(db, city, place, types=["restaurant", "liquor_store", "food"])

    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_bakery_with_wholesaler_type_is_not_flagged(db, city):
    # Same class of false positive: bakeries/cafes Google also tags
    # `wholesaler` (Paris Baguette, Mrs. Fields, The Plant Café Organic, etc.)
    place = _make_place(db, city, "The Plant Café Organic")
    _make_candidate(db, city, place, types=["bakery", "wholesaler", "point_of_interest"])

    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_actual_wholesaler_with_no_food_service_type_is_still_flagged(db, city):
    # The exemption only fires when a genuine food-service type is present.
    # A place with ONLY non-restaurant types is still real junk.
    place = _make_place(db, city, "Some Wholesale Depot")
    _make_candidate(db, city, place, types=["wholesaler", "point_of_interest"])

    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id in flagged_ids


# --------------------------------------------------------------------------
# In-store food concessions (name-check exemption) — the same false-positive
# shape as the Google-types exemption above, but for the belt-and-suspenders
# chain-name check: a Starbucks kiosk or AFC Sushi counter inside a Safeway
# is a distinct, real food-service business, not the host store itself.
# Found running this script for real against production.
# --------------------------------------------------------------------------

def test_costco_food_court_is_not_flagged_despite_costco_in_the_name(db, city):
    place = _make_place(db, city, "Costco Food Court")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_starbucks_inside_target_is_not_flagged(db, city):
    place = _make_place(db, city, "Starbucks (in Target)")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_afc_sushi_at_safeway_is_not_flagged(db, city):
    place = _make_place(db, city, "AFC SUSHI @ SAFEWAY #1953")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_target_cafe_is_not_flagged(db, city):
    place = _make_place(db, city, "Target Cafe")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_yummi_sushi_at_safeway_is_not_flagged(db, city):
    # A different concessionaire brand than AFC — same real food-service
    # business, caught by the broader "sushi" term instead of "afc ".
    place = _make_place(db, city, "YUMMI SUSHI @ SAFEWAY #910")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_starbuck_missing_trailing_s_is_not_flagged(db, city):
    # Real production row: the source data itself spells it "STARBUCK"
    # (missing the final letter). "starbuck" (not "starbucks") in the
    # exemption list still matches normal spellings as a substring too.
    place = _make_place(db, city, '"STARBUCK " SAFEWAY #910')
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id not in flagged_ids


def test_plain_costco_with_no_concession_signal_is_still_flagged(db, city):
    # Regression: the exemption must only fire for an actual concession
    # signal in the name, not just because SOME food-related word exists
    # anywhere in the broader catalog. Plain "Costco" is still real junk.
    place = _make_place(db, city, "Costco Wholesale #118")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id in flagged_ids


def test_costco_breakroom_canteen_is_still_flagged(db, city):
    # Deliberately NOT exempted: "canteen"/"breakroom" reads as an
    # employee-only cafeteria, not a public place to eat.
    place = _make_place(db, city, "Canteen @ Costco #1341 Breakroom")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id in flagged_ids


def test_food_sampling_program_is_still_flagged(db, city):
    # Deliberately NOT exempted: plain "food" isn't in the concession list
    # specifically so this doesn't get swept into the exemption — it's a
    # promotional sampling table, not a restaurant.
    place = _make_place(db, city, "Advantage Food Sampling Program @ Safeway #1502")
    flagged = _find_candidates_to_deactivate(db)
    flagged_ids = {p.id for p, _ in flagged}
    assert place.id in flagged_ids
