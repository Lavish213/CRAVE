"""
Coverage for app.services.discovery.overture_ingest_job — mirrors
test_osm_ingest_job.py's structure exactly, since overture_ingest_job.py is
a deliberate parallel of osm_ingest_job.py (second free acquisition source,
same ingest_candidate_v2 path downstream).

fetch_overture_places is always monkeypatched here — these tests must never
make a real network call to S3.
"""
from __future__ import annotations

import random
import sys
import uuid
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.discovery import overture_ingest_job
from app.services.discovery.overture_ingest_job import (
    BBOX_DEGREES,
    _rotation_offset,
    run_overture_city_ingest,
)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        # These tests commit real DiscoveryCandidate rows (via
        # run_overture_city_ingest -> ingest_candidate_v2 -> db.commit()) into
        # the on-disk SQLite file every test module in this suite shares.
        # Left uncleaned, a source="overture" row with confidence 0.8 (>=
        # promotion_orchestrator_v2.MIN_CONFIDENCE_THRESHOLD) is picked up by
        # any later-running test that queries DiscoveryCandidate globally —
        # e.g. test_promotion_pipeline_v2.py's
        # test_orchestrator_promotes_eligible_candidates, which counts
        # *every* eligible candidate in the table, not just its own. Only
        # this file ever writes source="overture" rows, so deleting them all
        # here is safe and doesn't touch any other test's data.
        session.query(DiscoveryCandidate).filter(
            DiscoveryCandidate.source == "overture"
        ).delete(synchronize_session=False)
        session.commit()
        session.close()


def _make_city(db, **overrides) -> City:
    defaults = dict(
        id=str(uuid.uuid4()),
        name="Overture Test City",
        slug=f"overture-test-{uuid.uuid4().hex[:8]}",
        lat=random.uniform(-60, 60),
        lng=random.uniform(-170, 170),
        is_active=True,
    )
    defaults.update(overrides)
    city = City(**defaults)
    db.add(city)
    db.commit()
    return city


def _place(*, external_id, name="Overture Test Restaurant", lat=51.5, lon=-0.12, **overrides):
    place = {
        "external_id": external_id,
        "name": name,
        "address": "123 Overture St",
        "lat": lat,
        "lon": lon,
        "phone": None,
        "website": None,
        "category_hint": "restaurant",
        "source": "overture",
        "confidence": 0.8,
        "raw_payload": {"category": "restaurant", "hierarchy": ["food_and_drink", "restaurant"]},
    }
    place.update(overrides)
    return place


def _matches_city_bbox(kwargs, city) -> bool:
    expected = {
        "lat_min": city.lat - BBOX_DEGREES,
        "lat_max": city.lat + BBOX_DEGREES,
        "lon_min": city.lng - BBOX_DEGREES,
        "lon_max": city.lng + BBOX_DEGREES,
    }
    return all(abs(kwargs[k] - expected[k]) < 1e-9 for k in expected)


def _fake_fetch_for_city(city, *, result=None, raises=None):
    def _fake(**kwargs):
        if _matches_city_bbox(kwargs, city):
            if raises is not None:
                raise raises
            return result or []
        return []

    return _fake


# ---------------------------------------------------------------------------
# _rotation_offset (pure function, no DB) — identical logic to OSM's
# ---------------------------------------------------------------------------

def test_rotation_offset_zero_when_nothing_to_scan():
    assert _rotation_offset(0, 5, date(2026, 1, 1)) == 0
    assert _rotation_offset(10, 0, date(2026, 1, 1)) == 0


def test_rotation_offset_stays_within_bounds_and_cycles():
    total, limit = 12, 5
    seen_offsets = {
        _rotation_offset(total, limit, date.fromordinal(o))
        for o in range(date(2026, 1, 1).toordinal(), date(2026, 1, 1).toordinal() + 10)
    }
    assert seen_offsets <= {0, 5, 10}


# ---------------------------------------------------------------------------
# run_overture_city_ingest
# ---------------------------------------------------------------------------

def test_run_overture_city_ingest_noop_when_limit_is_zero(db, monkeypatch):
    monkeypatch.setattr(
        overture_ingest_job, "fetch_overture_places",
        lambda **kw: (_ for _ in ()).throw(
            AssertionError("fetch_overture_places should not be called when limit<=0")
        ),
    )

    result = run_overture_city_ingest(db=db, limit=0, today=date(2026, 1, 1))
    assert result == {"cities_scanned": 0, "fetched": 0, "ingested": 0, "errors": 0}


def test_run_overture_city_ingest_ingests_fetched_places(db, monkeypatch):
    city = _make_city(db)
    external_id = f"overture:{uuid.uuid4().hex}"

    monkeypatch.setattr(
        overture_ingest_job, "fetch_overture_places",
        _fake_fetch_for_city(city, result=[_place(external_id=external_id)]),
    )

    result = run_overture_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))

    assert result["fetched"] == 1
    assert result["ingested"] == 1
    assert result["errors"] == 0

    candidate = (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.external_id == external_id)
        .one_or_none()
    )
    assert candidate is not None
    assert candidate.city_id == city.id
    assert candidate.source == "overture"
    assert candidate.confidence_score == 0.8


def test_run_overture_city_ingest_is_idempotent_by_external_id(db, monkeypatch):
    city = _make_city(db)
    external_id = f"overture:{uuid.uuid4().hex}"

    monkeypatch.setattr(
        overture_ingest_job, "fetch_overture_places",
        _fake_fetch_for_city(city, result=[_place(external_id=external_id)]),
    )

    run_overture_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))
    run_overture_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))

    rows = (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.external_id == external_id)
        .all()
    )
    assert len(rows) == 1


def test_run_overture_city_ingest_continues_after_a_fetch_failure(db, monkeypatch):
    city = _make_city(db)

    monkeypatch.setattr(
        overture_ingest_job, "fetch_overture_places",
        _fake_fetch_for_city(city, raises=RuntimeError("s3 unreachable")),
    )

    result = run_overture_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))

    assert result["fetched"] == 0
    assert result["ingested"] == 0
    assert result["errors"] == 1


def test_run_overture_city_ingest_skips_bad_place_but_ingests_the_rest(db, monkeypatch):
    city = _make_city(db)
    good_external_id = f"overture:{uuid.uuid4().hex}"

    monkeypatch.setattr(
        overture_ingest_job, "fetch_overture_places",
        _fake_fetch_for_city(city, result=[
            _place(external_id="overture:missing-name", name=None),
            _place(external_id=good_external_id),
        ]),
    )

    result = run_overture_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))

    assert result["fetched"] == 2
    assert result["ingested"] == 1
    assert result["errors"] == 1

    assert (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.external_id == good_external_id)
        .one_or_none()
        is not None
    )


def test_run_overture_city_ingest_respects_limit(db, monkeypatch):
    for _ in range(3):
        _make_city(db)

    monkeypatch.setattr(overture_ingest_job, "fetch_overture_places", lambda **kw: [])

    result = run_overture_city_ingest(db=db, limit=2, today=date(2026, 1, 1))
    assert result["cities_scanned"] <= 2
