"""
Coverage for scripts/backfill_osm_hours_and_seating.py -- the retroactive
fix for OSM-sourced places promoted before promote_service_v2.py learned
to read opening_hours/outdoor_seating out of the tags dict OSM always
returns (see test_promotion_pipeline_v2.py's
test_promote_writes_hours_and_outdoor_seating_claims_from_osm_tags).
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.db.models.discovery_candidate import DiscoveryCandidate

from scripts.backfill_osm_hours_and_seating import run_backfill


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
    c = City(slug=f"backfill-hours-test-{suffix}", name=f"Backfill Hours Test City {suffix}")
    db.add(c)
    db.commit()

    yield c

    place_ids = [row.id for row in db.query(Place.id).filter(Place.city_id == c.id).all()]
    if place_ids:
        db.query(PlaceTruth).filter(PlaceTruth.place_id.in_(place_ids)).delete(synchronize_session=False)
        db.query(PlaceClaim).filter(PlaceClaim.place_id.in_(place_ids)).delete(synchronize_session=False)
    db.query(Place).filter(Place.city_id == c.id).delete(synchronize_session=False)
    db.query(DiscoveryCandidate).filter(DiscoveryCandidate.city_id == c.id).delete(synchronize_session=False)
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _already_promoted_candidate(db, city, *, raw_payload, source="osm") -> tuple[Place, DiscoveryCandidate]:
    place = Place(name="Pre-existing OSM Place", city_id=city.id, lat=37.77, lng=-122.42)
    db.add(place)
    db.flush()

    candidate = DiscoveryCandidate(
        name="Pre-existing OSM Place", city_id=city.id, lat=37.77, lng=-122.42,
        source=source, resolved=True, resolved_place_id=place.id, status="promoted",
        raw_payload=raw_payload,
    )
    db.add(candidate)
    db.commit()
    return place, candidate


def test_backfill_writes_claims_and_truths_for_already_promoted_place(db, city):
    place, _ = _already_promoted_candidate(
        db, city, raw_payload={"opening_hours": "Mo-Fr 09:00-17:00", "outdoor_seating": "limited"},
    )

    result = run_backfill()

    assert result["claims_written"] == 2
    assert result["places_affected"] == 1

    truths = {
        t.truth_type: t.truth_value
        for t in db.query(PlaceTruth).filter(PlaceTruth.place_id == place.id)
    }
    assert truths["hours"] == "mo-fr 09:00-17:00"
    assert truths["outdoor_seating"] == "limited"


def test_backfill_is_idempotent_on_a_second_run(db, city):
    _already_promoted_candidate(
        db, city, raw_payload={"opening_hours": "24/7"},
    )

    first = run_backfill()
    second = run_backfill()

    assert first["claims_written"] == 1
    assert second["claims_written"] == 0


def test_backfill_skips_non_osm_sourced_candidates(db, city):
    _already_promoted_candidate(
        db, city, source="overture",
        raw_payload={"opening_hours": "24/7", "outdoor_seating": "yes"},
    )

    result = run_backfill()

    assert result["claims_written"] == 0
    assert result["places_affected"] == 0


def test_backfill_dry_run_writes_nothing(db, city):
    place, _ = _already_promoted_candidate(
        db, city, raw_payload={"opening_hours": "24/7"},
    )

    result = run_backfill(dry_run=True)

    assert result["claims_written"] == 1
    assert db.query(PlaceClaim).filter(PlaceClaim.place_id == place.id).count() == 0
    assert db.query(PlaceTruth).filter(PlaceTruth.place_id == place.id).count() == 0
