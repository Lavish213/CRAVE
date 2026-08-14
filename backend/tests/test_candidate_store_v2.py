"""
Coverage for app.services.discovery.candidate_store_v2.upsert_discovery_candidate_v2
— previously untested despite being the core write path for every discovery
source (OSM, Overture, Google Places, user corroboration).

Regression test for a real, confirmed production bug: the name+city
fallback match used .one_or_none(), which raises sqlalchemy.exc.
MultipleResultsFound the moment a city has more than one DiscoveryCandidate
row sharing a name — which is legitimate and common (two branches of the
same chain, or the same real place tagged twice by a source at slightly
different coordinates). Only (city_id, name, lat, lng) together is unique
(see uq_candidate_city_name_location on the model), not (city_id, name)
alone. Confirmed live in production: repeated osm_ingest_candidate_failed
crashes silently dropped every POI that hit this.

external_id is matched globally, not scoped to city (matches the model's
uq_candidate_external_source constraint) — every test below therefore uses
its own unique external_id so tests sharing this on-disk SQLite file can't
cross-match each other's rows.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.discovery.candidate_store_v2 import upsert_discovery_candidate_v2


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def city(db):
    # Teardown sweeps every DiscoveryCandidate row scoped to this city.
    # These tests commit real candidates (some with confidence_score >=
    # promotion_orchestrator_v2.MIN_CONFIDENCE_THRESHOLD) into the on-disk
    # SQLite file every test module in this suite shares — left uncleaned,
    # test_promotion_pipeline_v2.py's tests (which query DiscoveryCandidate
    # globally, no scoping of their own) pick them up and their promoted
    # counts go wrong. Same class of bug as the teardown added for
    # test_overture_ingest_job.py.
    c = City(
        id=str(uuid.uuid4()),
        name="Candidate Store Test City",
        slug=f"candidate-store-test-{uuid.uuid4().hex[:8]}",
        lat=37.7749,
        lng=-122.4194,
        is_active=True,
    )
    db.add(c)
    db.commit()

    yield c

    db.query(DiscoveryCandidate).filter(DiscoveryCandidate.city_id == c.id).delete(
        synchronize_session=False
    )
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _eid() -> str:
    return f"osm:way:{uuid.uuid4().hex[:12]}"


def test_creates_new_candidate_when_none_exists(db, city):
    candidate = upsert_discovery_candidate_v2(
        db=db, name="Millie's", city_id=city.id, lat=37.77, lng=-122.42,
        source="osm", confidence_score=0.75,
    )
    db.commit()

    assert candidate.id is not None
    assert candidate.name == "Millie's"
    assert candidate.confidence_score == 0.75


def test_updates_existing_by_external_id(db, city):
    eid = _eid()
    first = upsert_discovery_candidate_v2(
        db=db, name="Millie's", city_id=city.id, external_id=eid,
        source="osm", confidence_score=0.6,
    )
    db.commit()

    second = upsert_discovery_candidate_v2(
        db=db, name="Millie's", city_id=city.id, external_id=eid,
        source="osm", confidence_score=0.9, website="https://millies.example.com",
    )
    db.commit()

    assert second.id == first.id
    assert second.confidence_score == 0.9
    assert second.website == "https://millies.example.com"

    rows = db.query(DiscoveryCandidate).filter(DiscoveryCandidate.city_id == city.id).all()
    assert len(rows) == 1


def test_fallback_match_finds_single_existing_by_name_and_city(db, city):
    unique_name = f"Millie's {uuid.uuid4().hex[:8]}"
    first = upsert_discovery_candidate_v2(
        db=db, name=unique_name, city_id=city.id, external_id=_eid(),
        source="osm", confidence_score=0.6,
    )
    db.commit()

    # No external_id this time -> must fall back to name+city matching.
    second = upsert_discovery_candidate_v2(
        db=db, name=unique_name, city_id=city.id, source="osm", confidence_score=0.75,
    )
    db.commit()

    assert second.id == first.id
    rows = db.query(DiscoveryCandidate).filter(DiscoveryCandidate.city_id == city.id).all()
    assert len(rows) == 1


def test_fallback_match_does_not_crash_when_multiple_rows_share_a_name(db, city):
    """The actual regression. Two rows sharing (city_id, name) but with
    different lat/lng are inserted directly here (bypassing the upsert path
    for setup) to simulate the real production precondition — two branches
    of the same chain, or the same place independently entered twice by
    different sources/times before ever colliding. Going through
    upsert_discovery_candidate_v2 for both inserts wouldn't reproduce this:
    its own name+city fallback would merge the second call onto the first
    row rather than create a second one, which is correct steady-state
    behavior but means the "already have 2 duplicate rows" precondition has
    to be set up directly, matching how it actually arose in production."""
    unique_name = f"Millie's {uuid.uuid4().hex[:8]}"
    from datetime import datetime, timedelta, timezone

    now = datetime.now(timezone.utc)
    row_a = DiscoveryCandidate(
        id=str(uuid.uuid4()), external_id=_eid(), source="osm",
        name=unique_name, city_id=city.id, lat=37.70, lng=-122.40,
        confidence_score=0.6, status="candidate", resolved=False, blocked=False,
        created_at=now, updated_at=now,
    )
    row_b = DiscoveryCandidate(
        id=str(uuid.uuid4()), external_id=_eid(), source="osm",
        name=unique_name, city_id=city.id, lat=37.80, lng=-122.50,
        confidence_score=0.6, status="candidate", resolved=False, blocked=False,
        created_at=now + timedelta(seconds=5), updated_at=now + timedelta(seconds=5),
    )
    db.add_all([row_a, row_b])
    db.commit()

    # An upsert with no external_id hits the name+city fallback, which now
    # matches TWO rows. Must not raise MultipleResultsFound.
    result = upsert_discovery_candidate_v2(
        db=db, name=unique_name, city_id=city.id, source="osm", confidence_score=0.9,
    )
    db.commit()

    assert result.id == row_a.id  # deterministic: oldest (created_at asc) wins
    assert result.confidence_score == 0.9

    # Still exactly 2 rows — the fallback updated the existing one in place,
    # it did not create a third.
    rows_after = (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.city_id == city.id, DiscoveryCandidate.name == unique_name)
        .all()
    )
    assert len(rows_after) == 2


def test_automated_source_confidence_uses_max_not_sum_on_rescan(db, city):
    eid = _eid()
    upsert_discovery_candidate_v2(
        db=db, name="Millie's", city_id=city.id, external_id=eid,
        source="osm", confidence_score=0.75,
    )
    db.commit()

    # Re-scan by the same automated source with a lower confidence must not
    # decrease the stored value.
    result = upsert_discovery_candidate_v2(
        db=db, name="Millie's", city_id=city.id, external_id=eid,
        source="osm", confidence_score=0.5,
    )
    db.commit()

    assert result.confidence_score == 0.75


def test_user_corroboration_accumulates_confidence_across_distinct_contributors(db, city):
    eid = _eid()
    upsert_discovery_candidate_v2(
        db=db, name="Millie's", city_id=city.id, external_id=eid,
        source="user_gps", confidence_score=0.35, contributor_key="user_gps:user-a",
    )
    db.commit()

    result = upsert_discovery_candidate_v2(
        db=db, name="Millie's", city_id=city.id, external_id=eid,
        source="user_gps", confidence_score=0.35, contributor_key="user_gps:user-b",
    )
    db.commit()

    assert result.confidence_score == pytest.approx(0.70)
