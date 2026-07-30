"""
Real coverage for the v2 discovery/promotion pipeline — this file and
tests/test_truth_resolver_v2.py were both 0 bytes before this pass (a
directory listing made discovery_candidates -> places promotion look
tested when it had zero real assertions).

Covers the two live modules the scheduler actually calls (see
app/scheduler.py::_job_discovery -> run_discovery_pipeline_v2 ->
promote_ready_candidates_v2 -> promote_candidate_v2):

  - app.services.discovery.promote_service_v2.promote_candidate_v2
  - app.services.discovery.promotion_orchestrator_v2.promote_ready_candidates_v2

Deliberately does NOT test app.services.discovery.promotion_gate_v2 —
that module's own header comment confirms it's dead code (never imported
by the live path; the orchestrator has its own inline filtering instead).
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.discovery.promote_service_v2 import promote_candidate_v2
from app.services.discovery import promotion_orchestrator_v2
from app.services.discovery.promotion_orchestrator_v2 import (
    promote_ready_candidates_v2,
    MIN_CONFIDENCE_THRESHOLD,
    MAX_FAILURES_BEFORE_BLOCK,
)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_city(db) -> City:
    city = City(
        id=str(uuid.uuid4()),
        name="Promotion Test City",
        slug=f"promo-test-{uuid.uuid4().hex[:8]}",
        lat=37.8,
        lng=-122.27,
        is_active=True,
    )
    db.add(city)
    db.commit()
    return city


def _make_candidate(db, city, **overrides) -> DiscoveryCandidate:
    defaults = dict(
        id=str(uuid.uuid4()),
        name=f"Test Diner {uuid.uuid4().hex[:8]}",
        city_id=city.id,
        lat=37.8044,
        lng=-122.2712,
        address=None,
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
# promote_candidate_v2
# ---------------------------------------------------------------------------

def test_promote_candidate_returns_none_for_missing_candidate(db):
    assert promote_candidate_v2(db=db, candidate_id=str(uuid.uuid4())) is None


def test_promote_candidate_creates_new_place_and_writes_claims_and_truths(db):
    city = _make_city(db)
    candidate = _make_candidate(db, city, name="Brand New Spot")

    place_id = promote_candidate_v2(db=db, candidate_id=candidate.id)
    # promote_candidate_v2 only flushes (the orchestrator commits between
    # candidates — see promote_ready_candidates_v2). Commit explicitly here
    # so the change survives this test's session close instead of rolling
    # back and leaving a phantom eligible candidate for later tests' global,
    # unscoped queries to pick up.
    db.commit()

    assert place_id is not None

    place = db.get(Place, place_id)
    assert place is not None
    assert place.city_id == city.id
    assert place.lat == candidate.lat
    assert place.lng == candidate.lng

    db.refresh(candidate)
    assert candidate.resolved is True
    assert candidate.resolved_place_id == place_id
    assert candidate.status == "promoted"
    assert candidate.promoted_at is not None

    claim_fields = {
        c.field
        for c in db.query(PlaceClaim).filter(PlaceClaim.place_id == place_id).all()
    }
    assert {"name", "lat", "lng"} <= claim_fields

    truth_types = {
        t.truth_type
        for t in db.query(PlaceTruth).filter(PlaceTruth.place_id == place_id).all()
    }
    assert {"name", "lat", "lng"} <= truth_types


def test_promote_candidate_already_resolved_is_idempotent(db):
    city = _make_city(db)
    place = Place(
        id=str(uuid.uuid4()),
        name="Already Promoted Place",
        city_id=city.id,
        lat=37.8,
        lng=-122.27,
        is_active=True,
    )
    db.add(place)
    db.commit()

    candidate = _make_candidate(
        db, city,
        resolved=True,
        resolved_place_id=place.id,
        status="promoted",
    )

    result = promote_candidate_v2(db=db, candidate_id=candidate.id)
    assert result == place.id


def test_promote_candidate_merges_into_matching_place_by_website_domain(db):
    """
    entity_match requires a name match plus one strong signal (address or
    website domain) or a geo fallback. Same exact name + same website
    domain guarantees a match regardless of the two lat/lng values, so
    this deterministically exercises the merge branch instead of creating
    a duplicate Place.
    """
    city = _make_city(db)

    existing_place = Place(
        id=str(uuid.uuid4()),
        name="Merge Test Diner",
        city_id=city.id,
        lat=10.0,
        lng=20.0,
        website="https://mergetestdiner.com",
        address=None,
        is_active=True,
    )
    db.add(existing_place)
    db.commit()

    candidate = _make_candidate(
        db, city,
        name="Merge Test Diner",
        lat=10.5,
        lng=20.5,
        address="123 Test St",
        website="https://mergetestdiner.com/menu",
    )

    place_id = promote_candidate_v2(db=db, candidate_id=candidate.id)
    db.commit()  # see comment in the "creates new place" test above

    assert place_id == existing_place.id

    same_name_places = (
        db.query(Place)
        .filter(Place.city_id == city.id, Place.name == "Merge Test Diner")
        .all()
    )
    assert len(same_name_places) == 1

    db.refresh(existing_place)
    assert existing_place.address == "123 Test St"


# ---------------------------------------------------------------------------
# promote_ready_candidates_v2
# ---------------------------------------------------------------------------

def test_promote_ready_candidates_skips_low_confidence_blocked_and_promoted(db):
    city = _make_city(db)

    eligible = _make_candidate(db, city, name="Eligible Spot", confidence_score=0.9)
    low_confidence = _make_candidate(
        db, city, name="Low Confidence Spot",
        confidence_score=MIN_CONFIDENCE_THRESHOLD - 0.1,
    )
    blocked = _make_candidate(
        db, city, name="Blocked Spot", confidence_score=0.95, blocked=True,
    )
    already_promoted = _make_candidate(
        db, city, name="Already Promoted Spot", confidence_score=0.95,
        status="promoted", resolved=True,
    )

    promoted_count = promote_ready_candidates_v2(db=db, limit=10)

    assert promoted_count == 1

    db.refresh(eligible)
    db.refresh(low_confidence)
    db.refresh(blocked)
    db.refresh(already_promoted)

    assert eligible.status == "promoted"
    assert eligible.resolved_place_id is not None

    assert low_confidence.status == "candidate"
    assert blocked.status == "candidate"
    assert already_promoted.resolved_place_id is None


def test_promote_ready_candidates_respects_limit(db):
    city = _make_city(db)
    candidates = [
        _make_candidate(db, city, name=f"Limit Test Spot {i}", confidence_score=0.9)
        for i in range(3)
    ]

    promoted_count = promote_ready_candidates_v2(db=db, limit=2)
    assert promoted_count == 2

    statuses = []
    for c in candidates:
        db.refresh(c)
        statuses.append(c.status)

    assert statuses.count("promoted") == 2
    assert statuses.count("candidate") == 1


def test_promote_ready_candidates_records_failure_with_backoff(db, monkeypatch):
    city = _make_city(db)
    candidate = _make_candidate(db, city, name="Flaky Spot", confidence_score=0.9)

    def _boom(*, db, candidate_id):
        raise RuntimeError("simulated promotion failure")

    monkeypatch.setattr(promotion_orchestrator_v2, "promote_candidate_v2", _boom)

    promoted_count = promote_ready_candidates_v2(db=db, limit=10)
    assert promoted_count == 0

    db.refresh(candidate)
    assert candidate.failure_count == 1
    assert candidate.blocked is False
    assert "simulated promotion failure" in (candidate.last_error or "")
    assert candidate.next_retry_at is not None
    # SQLite has no native tz-aware storage — a DateTime(timezone=True)
    # column round-trips as naive UTC on read, even though the value was
    # written from an aware datetime. Compare against naive UTC to match.
    assert candidate.next_retry_at > datetime.utcnow()


def test_promote_ready_candidates_dead_letters_after_max_failures(db, monkeypatch):
    city = _make_city(db)
    candidate = _make_candidate(
        db, city, name="Terminally Flaky Spot", confidence_score=0.9,
        failure_count=MAX_FAILURES_BEFORE_BLOCK - 1,
        next_retry_at=None,
    )

    def _boom(*, db, candidate_id):
        raise RuntimeError("simulated terminal failure")

    monkeypatch.setattr(promotion_orchestrator_v2, "promote_candidate_v2", _boom)

    promoted_count = promote_ready_candidates_v2(db=db, limit=10)
    assert promoted_count == 0

    db.refresh(candidate)
    assert candidate.failure_count == MAX_FAILURES_BEFORE_BLOCK
    assert candidate.blocked is True


def test_promote_ready_candidates_returns_zero_when_nothing_eligible(db):
    city = _make_city(db)
    _make_candidate(db, city, name="Blocked Only", blocked=True, confidence_score=0.9)

    assert promote_ready_candidates_v2(db=db, limit=10) == 0
