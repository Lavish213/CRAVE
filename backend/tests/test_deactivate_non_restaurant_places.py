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
