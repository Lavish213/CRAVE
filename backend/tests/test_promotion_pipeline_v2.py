# tests/test_promotion_pipeline_v2.py
"""
Tests for the live v2 promotion pipeline:
  - app.services.discovery.promote_service_v2.promote_candidate_v2
  - app.services.discovery.promotion_orchestrator_v2.promote_ready_candidates_v2

This file was previously 0 bytes. This is the pipeline that actually runs
(app/scheduler.py calls promote_ready_candidates_v2) — it turns a scraped
DiscoveryCandidate into a canonical Place, dedupes against existing places,
writes the core claims, resolves truths, and tracks per-candidate failures
with backoff/dead-lettering. None of that had test coverage.

(app/pipeline/promotion_engine.py is a separate, explicitly-dead module —
not tested here; see its own docstring.)

External geocoding (nominatim search_place) is mocked — these are unit
tests for the promotion/dedup/failure-handling logic, not network tests.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.db.models.discovery_candidate import DiscoveryCandidate

from app.services.discovery.promote_service_v2 import promote_candidate_v2
from app.services.discovery.promotion_orchestrator_v2 import (
    promote_ready_candidates_v2,
    MIN_CONFIDENCE_THRESHOLD,
    MAX_FAILURES_BEFORE_BLOCK,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def city(db):
    """Throwaway City; teardown sweeps every Place/Candidate/Claim/Truth
    scoped to it, regardless of what an individual test created."""
    suffix = uuid.uuid4().hex[:8]
    c = City(slug=f"promo-test-{suffix}", name=f"Promo Test City {suffix}")
    db.add(c)
    db.commit()

    yield c

    place_ids = [
        row.id for row in db.query(Place.id).filter(Place.city_id == c.id).all()
    ]
    if place_ids:
        db.query(PlaceTruth).filter(PlaceTruth.place_id.in_(place_ids)).delete(
            synchronize_session=False
        )
        db.query(PlaceClaim).filter(PlaceClaim.place_id.in_(place_ids)).delete(
            synchronize_session=False
        )
    db.query(Place).filter(Place.city_id == c.id).delete(synchronize_session=False)
    db.query(DiscoveryCandidate).filter(DiscoveryCandidate.city_id == c.id).delete(
        synchronize_session=False
    )
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_candidate(db, city_id: str, **overrides) -> DiscoveryCandidate:
    suffix = uuid.uuid4().hex[:8]
    defaults = dict(
        name=f"Test Candidate {suffix}",
        city_id=city_id,
        lat=37.7749,
        lng=-122.4194,
        address=f"{suffix} Market St",
        website=None,
        confidence_score=0.9,
        status="candidate",
        resolved=False,
        blocked=False,
    )
    defaults.update(overrides)
    candidate = DiscoveryCandidate(**defaults)
    db.add(candidate)
    db.commit()
    return candidate


# ---------------------------------------------------------------------------
# promote_candidate_v2 — core behavior
# ---------------------------------------------------------------------------

def test_promote_unknown_candidate_returns_none(db):
    assert promote_candidate_v2(db=db, candidate_id="not-a-real-id") is None


def test_promote_already_resolved_candidate_reresolves_truths(db, city):
    """If resolved_place_id is already set, promote_candidate_v2 short-
    circuits straight to re-resolving truths for that place instead of
    re-running the full promotion flow — verifies both the short-circuit
    and that it still does real work (a PlaceTruth gets written)."""
    place = Place(name="Already Resolved Place", city_id=city.id,
                   lat=37.0, lng=-122.0)
    db.add(place)
    db.flush()
    db.add(PlaceClaim(
        place_id=place.id, field="name", claim_key="k1",
        value_text="Already Resolved Place", confidence=0.9, source="test",
    ))
    db.commit()

    candidate = _make_candidate(
        db, city.id, resolved=True, resolved_place_id=place.id, status="promoted",
    )

    result = promote_candidate_v2(db=db, candidate_id=candidate.id)

    assert result == place.id
    truth = (
        db.query(PlaceTruth)
        .filter(PlaceTruth.place_id == place.id, PlaceTruth.truth_type == "name")
        .one_or_none()
    )
    assert truth is not None
    # Inserted straight as a PlaceClaim here (bypassing normalize_claim, which
    # lowercases) — so this checks the resolver preserves the claim's value
    # verbatim, not that it re-normalizes it.
    assert truth.truth_value == "Already Resolved Place"


def test_promote_creates_new_place_when_no_match(db, city):
    candidate = _make_candidate(db, city.id, name="Brand New Diner",
                                 address="100 Main St")

    place_id = promote_candidate_v2(db=db, candidate_id=candidate.id)

    assert place_id is not None
    place = db.query(Place).filter(Place.id == place_id).one()
    assert place.name == "Brand New Diner"
    assert place.city_id == city.id

    db.refresh(candidate)
    assert candidate.resolved is True
    assert candidate.resolved_place_id == place_id
    assert candidate.status == "promoted"
    assert candidate.promoted_at is not None

    # Core claims (name, lat, lng) were written and resolved into truths.
    claim_fields = {
        c.field for c in db.query(PlaceClaim).filter(PlaceClaim.place_id == place_id)
    }
    assert {"name", "lat", "lng"}.issubset(claim_fields)

    truth_types = {
        t.truth_type for t in db.query(PlaceTruth).filter(PlaceTruth.place_id == place_id)
    }
    assert {"name", "lat", "lng"}.issubset(truth_types)


def test_promote_merges_into_existing_place_on_name_and_address_match(db, city):
    existing = Place(
        name="Horn Barbecue", city_id=city.id,
        lat=37.77, lng=-122.42, address="20 Pier Ave",
    )
    db.add(existing)
    db.commit()

    candidate = _make_candidate(
        db, city.id, name="Horn Barbecue", address="20 Pier Ave",
        lat=37.77, lng=-122.42,
    )

    place_id = promote_candidate_v2(db=db, candidate_id=candidate.id)

    assert place_id == existing.id
    # No second Place should have been created for the same city.
    matches = db.query(Place).filter(
        Place.city_id == city.id, Place.name == "Horn Barbecue"
    ).all()
    assert len(matches) == 1


def test_promote_keeps_distinct_same_name_branches_in_one_city(db, city):
    """A chain can legitimately have multiple locations in one city.

    The entity matcher correctly rejects a merge when address and location
    disagree, so persistence must also permit both canonical places.
    """
    first = _make_candidate(
        db,
        city.id,
        name="Branch Cafe",
        address="100 First St",
        lat=37.7700,
        lng=-122.4200,
    )
    second = _make_candidate(
        db,
        city.id,
        name="Branch Cafe",
        address="900 Ninth St",
        lat=37.7900,
        lng=-122.4000,
    )

    first_place_id = promote_candidate_v2(db=db, candidate_id=first.id)
    db.commit()
    second_place_id = promote_candidate_v2(db=db, candidate_id=second.id)
    db.commit()

    assert first_place_id != second_place_id
    branches = db.query(Place).filter(
        Place.city_id == city.id,
        Place.name == "Branch Cafe",
    ).all()
    assert {p.address for p in branches} == {"100 First St", "900 Ninth St"}


def test_promote_backfills_missing_fields_on_existing_place(db, city):
    existing = Place(
        name="Bare Place", city_id=city.id, lat=37.77, lng=-122.42,
        address=None, website=None,
    )
    db.add(existing)
    db.commit()

    candidate = _make_candidate(
        db, city.id, name="Bare Place", lat=37.77, lng=-122.42,
        address="55 Filled St", website="https://bareplace.example.com",
    )

    place_id = promote_candidate_v2(db=db, candidate_id=candidate.id)
    db.refresh(existing)

    assert place_id == existing.id
    assert existing.address == "55 Filled St"
    assert existing.website == "https://bareplace.example.com"


def test_promote_geocodes_when_coords_missing(db, city):
    candidate = _make_candidate(db, city.id, name="Needs Geocode", lat=None, lng=None)

    with patch(
        "app.services.discovery.promote_service_v2.search_place",
        return_value={"lat": "40.7128", "lon": "-74.0060"},
    ) as mock_search:
        place_id = promote_candidate_v2(db=db, candidate_id=candidate.id)

    mock_search.assert_called_once()
    assert place_id is not None
    place = db.query(Place).filter(Place.id == place_id).one()
    assert place.lat == pytest.approx(40.7128)
    assert place.lng == pytest.approx(-74.0060)

    db.refresh(candidate)
    assert candidate.lat == pytest.approx(40.7128)
    assert candidate.lng == pytest.approx(-74.0060)


def test_promote_returns_none_when_geocode_fails(db, city):
    candidate = _make_candidate(db, city.id, name="Ungeocodable", lat=None, lng=None)

    with patch(
        "app.services.discovery.promote_service_v2.search_place",
        return_value=None,
    ):
        result = promote_candidate_v2(db=db, candidate_id=candidate.id)

    assert result is None
    db.refresh(candidate)
    assert candidate.resolved is False
    assert candidate.resolved_place_id is None


# ---------------------------------------------------------------------------
# promote_ready_candidates_v2 — orchestrator: filtering, limits, batching
# ---------------------------------------------------------------------------

def test_orchestrator_promotes_eligible_candidates(db, city):
    _make_candidate(db, city.id, confidence_score=0.9)
    _make_candidate(db, city.id, confidence_score=0.9)

    promoted = promote_ready_candidates_v2(db=db, limit=10)

    assert promoted == 2


def test_orchestrator_skips_below_confidence_threshold(db, city):
    _make_candidate(db, city.id, confidence_score=MIN_CONFIDENCE_THRESHOLD - 0.1)

    promoted = promote_ready_candidates_v2(db=db, limit=10)

    assert promoted == 0


def test_orchestrator_skips_blocked_candidates(db, city):
    _make_candidate(db, city.id, confidence_score=0.9, blocked=True)

    promoted = promote_ready_candidates_v2(db=db, limit=10)

    assert promoted == 0


def test_orchestrator_skips_already_resolved(db, city):
    _make_candidate(db, city.id, confidence_score=0.9, resolved=True)

    promoted = promote_ready_candidates_v2(db=db, limit=10)

    assert promoted == 0


def test_orchestrator_respects_limit(db, city):
    for _ in range(3):
        _make_candidate(db, city.id, confidence_score=0.9)

    promoted = promote_ready_candidates_v2(db=db, limit=2)

    assert promoted == 2


def test_orchestrator_skips_candidates_still_in_backoff(db, city):
    _make_candidate(
        db, city.id, confidence_score=0.9,
        next_retry_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )

    promoted = promote_ready_candidates_v2(db=db, limit=10)

    assert promoted == 0


def test_orchestrator_records_failure_and_sets_backoff(db, city):
    candidate = _make_candidate(db, city.id, confidence_score=0.9)

    with patch(
        "app.services.discovery.promotion_orchestrator_v2.promote_candidate_v2",
        side_effect=RuntimeError("boom"),
    ):
        promoted = promote_ready_candidates_v2(db=db, limit=10)

    assert promoted == 0
    db.refresh(candidate)
    assert candidate.failure_count == 1
    assert candidate.last_error is not None and "boom" in candidate.last_error
    assert candidate.next_retry_at is not None
    assert candidate.blocked is False


def test_orchestrator_dead_letters_after_max_failures(db, city):
    candidate = _make_candidate(
        db, city.id, confidence_score=0.9,
        failure_count=MAX_FAILURES_BEFORE_BLOCK - 1,
    )

    with patch(
        "app.services.discovery.promotion_orchestrator_v2.promote_candidate_v2",
        side_effect=RuntimeError("still broken"),
    ):
        promote_ready_candidates_v2(db=db, limit=10)

    db.refresh(candidate)
    assert candidate.failure_count == MAX_FAILURES_BEFORE_BLOCK
    assert candidate.blocked is True


def test_orchestrator_one_failure_does_not_block_other_candidates(db, city):
    """Per-candidate commit/rollback isolation: one candidate raising must
    not roll back or block a different candidate's successful promotion."""
    bad = _make_candidate(db, city.id, confidence_score=0.9, name="Bad Candidate")
    good = _make_candidate(db, city.id, confidence_score=0.9, name="Good Candidate")

    real_promote = promote_candidate_v2

    def _side_effect(*, db, candidate_id):
        if candidate_id == bad.id:
            raise RuntimeError("bad candidate exploded")
        return real_promote(db=db, candidate_id=candidate_id)

    with patch(
        "app.services.discovery.promotion_orchestrator_v2.promote_candidate_v2",
        side_effect=_side_effect,
    ):
        promoted = promote_ready_candidates_v2(db=db, limit=10)

    assert promoted == 1
    db.refresh(good)
    db.refresh(bad)
    assert good.resolved is True
    assert bad.resolved is False
    assert bad.failure_count == 1


def test_orchestrator_no_eligible_candidates_returns_zero(db, city):
    assert promote_ready_candidates_v2(db=db, limit=10) == 0


def test_orchestrator_zero_limit_returns_zero_without_querying(db, city):
    _make_candidate(db, city.id, confidence_score=0.9)
    assert promote_ready_candidates_v2(db=db, limit=0) == 0
