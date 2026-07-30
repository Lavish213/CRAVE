"""
Coverage for app.services.discovery.osm_ingest_job — the previously-missing
acquisition half of the discovery pipeline (see app/scheduler.py::
_job_discovery, which only ever promoted candidates already sitting in
discovery_candidates; nothing scheduled fetched new ones from OSM/Overpass
or anywhere else).

fetch_osm_pois is always monkeypatched here — these tests must never make
a real network call to the public Overpass API.

The fake fetch functions below key off the requested bbox rather than
returning the same canned result unconditionally. tests/conftest.py seeds
one active city up front, and other test modules in this suite create
their own active cities too (all share one on-disk SQLite file for the
whole run) — run_osm_city_ingest's query has no per-test scoping, so a
bbox-blind fake would sweep in whatever other cities happen to be active
at the time and make the fetched/ingested/errors counts depend on
collection order. Matching on bbox makes every assertion here exact
regardless of what else is in the table.
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
from app.services.discovery import osm_ingest_job
from app.services.discovery.osm_ingest_job import (
    BBOX_DEGREES,
    _rotation_offset,
    run_osm_city_ingest,
)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_city(db, **overrides) -> City:
    # Each test's city needs its own bbox — see the module docstring on
    # _fake_fetch_for_city / _matches_city_bbox for why a shared lat/lng
    # across tests would break the isolation trick (every city sharing one
    # bbox would all match the same test's fake, inflating fetched/errors
    # counts by however many earlier tests' cities are still in the table).
    defaults = dict(
        id=str(uuid.uuid4()),
        name="OSM Test City",
        slug=f"osm-test-{uuid.uuid4().hex[:8]}",
        lat=random.uniform(-60, 60),
        lng=random.uniform(-170, 170),
        is_active=True,
    )
    defaults.update(overrides)
    city = City(**defaults)
    db.add(city)
    db.commit()
    return city


def _poi(*, external_id, name="OSM Test Restaurant", lat=51.5, lon=-0.12, **overrides):
    poi = {
        "external_id": external_id,
        "name": name,
        "address": "123 OSM St",
        "lat": lat,
        "lon": lon,
        "phone": None,
        "website": None,
        "category_hint": "restaurant",
        "source": "osm",
        "confidence": 0.6,
        "raw_payload": {"amenity": "restaurant"},
    }
    poi.update(overrides)
    return poi


def _matches_city_bbox(kwargs, city) -> bool:
    expected = {
        "lat_min": city.lat - BBOX_DEGREES,
        "lat_max": city.lat + BBOX_DEGREES,
        "lon_min": city.lng - BBOX_DEGREES,
        "lon_max": city.lng + BBOX_DEGREES,
    }
    return all(abs(kwargs[k] - expected[k]) < 1e-9 for k in expected)


def _fake_fetch_for_city(city, *, result=None, raises=None):
    """Return the given result (or raise) only for `city`'s exact bbox;
    every other city in the scanned slice gets an empty list, exactly
    like a real Overpass query for an area with nothing matching."""

    def _fake(**kwargs):
        if _matches_city_bbox(kwargs, city):
            if raises is not None:
                raise raises
            return result or []
        return []

    return _fake


# ---------------------------------------------------------------------------
# _rotation_offset (pure function, no DB)
# ---------------------------------------------------------------------------

def test_rotation_offset_zero_when_nothing_to_scan():
    assert _rotation_offset(0, 5, date(2026, 1, 1)) == 0
    assert _rotation_offset(10, 0, date(2026, 1, 1)) == 0


def test_rotation_offset_stays_within_bounds_and_cycles():
    total, limit = 12, 5  # 3 pages: [0,5), [5,10), [10,12)
    seen_offsets = {
        _rotation_offset(total, limit, date.fromordinal(o))
        for o in range(date(2026, 1, 1).toordinal(), date(2026, 1, 1).toordinal() + 10)
    }
    assert seen_offsets <= {0, 5, 10}


# ---------------------------------------------------------------------------
# run_osm_city_ingest
# ---------------------------------------------------------------------------

def test_run_osm_city_ingest_noop_when_limit_is_zero(db, monkeypatch):
    monkeypatch.setattr(
        osm_ingest_job, "fetch_osm_pois",
        lambda **kw: (_ for _ in ()).throw(
            AssertionError("fetch_osm_pois should not be called when limit<=0")
        ),
    )

    result = run_osm_city_ingest(db=db, limit=0, today=date(2026, 1, 1))
    assert result == {"cities_scanned": 0, "fetched": 0, "ingested": 0, "errors": 0}


def test_run_osm_city_ingest_ingests_fetched_pois(db, monkeypatch):
    city = _make_city(db)
    external_id = f"osm:node:{uuid.uuid4().hex[:10]}"

    monkeypatch.setattr(
        osm_ingest_job, "fetch_osm_pois",
        _fake_fetch_for_city(city, result=[_poi(external_id=external_id)]),
    )

    result = run_osm_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))

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
    assert candidate.source == "osm"


def test_run_osm_city_ingest_is_idempotent_by_external_id(db, monkeypatch):
    city = _make_city(db)
    external_id = f"osm:node:{uuid.uuid4().hex[:10]}"

    monkeypatch.setattr(
        osm_ingest_job, "fetch_osm_pois",
        _fake_fetch_for_city(city, result=[_poi(external_id=external_id)]),
    )

    run_osm_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))
    run_osm_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))

    rows = (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.external_id == external_id)
        .all()
    )
    assert len(rows) == 1


def test_run_osm_city_ingest_continues_after_a_fetch_failure(db, monkeypatch):
    city = _make_city(db)

    monkeypatch.setattr(
        osm_ingest_job, "fetch_osm_pois",
        _fake_fetch_for_city(city, raises=RuntimeError("overpass unreachable")),
    )

    result = run_osm_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))

    assert result["fetched"] == 0
    assert result["ingested"] == 0
    assert result["errors"] == 1


def test_run_osm_city_ingest_skips_bad_poi_but_ingests_the_rest(db, monkeypatch):
    city = _make_city(db)
    good_external_id = f"osm:node:{uuid.uuid4().hex[:10]}"

    # A POI with no name can't be ingested (ingest_candidate_v2 raises
    # ValueError) — that must not stop the rest of the batch.
    monkeypatch.setattr(
        osm_ingest_job, "fetch_osm_pois",
        _fake_fetch_for_city(city, result=[
            _poi(external_id="osm:node:missing-name", name=None),
            _poi(external_id=good_external_id),
        ]),
    )

    result = run_osm_city_ingest(db=db, limit=1000, today=date(2026, 1, 1))

    assert result["fetched"] == 2
    assert result["ingested"] == 1
    assert result["errors"] == 1

    assert (
        db.query(DiscoveryCandidate)
        .filter(DiscoveryCandidate.external_id == good_external_id)
        .one_or_none()
        is not None
    )


def test_run_osm_city_ingest_respects_limit(db, monkeypatch):
    for _ in range(3):
        _make_city(db)

    monkeypatch.setattr(osm_ingest_job, "fetch_osm_pois", lambda **kw: [])

    result = run_osm_city_ingest(db=db, limit=2, today=date(2026, 1, 1))
    assert result["cities_scanned"] <= 2
