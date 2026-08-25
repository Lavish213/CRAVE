"""
Coverage for recommendation_event_service.py -- the Recommendation
Ledger's write side (see app/db/models/recommendation_event.py for the
full rationale). Covers the per-event validation/clamping logic directly
(no FastAPI layer), plus a DB round-trip for record_events().
"""
from __future__ import annotations

import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.recommendation_event import RecommendationEvent
from app.services.recommendations.recommendation_event_service import (
    build_valid_events,
    record_events,
    record_rank_outcome,
)


@dataclass
class _RawEvent:
    surface: Optional[str] = "feed"
    event_type: Optional[str] = "impression"
    place_id: Optional[str] = None
    position: Optional[int] = None
    rank_percentile: Optional[float] = None
    query: Optional[str] = None
    city_id: Optional[str] = None
    session_id: Optional[str] = None
    client_event_id: Optional[str] = None


def test_valid_event_passes_through():
    events = build_valid_events(
        raw_events=[_RawEvent(surface="feed", event_type="impression", position=3)],
        user_id="user-a",
    )
    assert len(events) == 1
    assert events[0].surface == "feed"
    assert events[0].event_type == "impression"
    assert events[0].position == 3
    assert events[0].user_id == "user-a"


def test_unknown_surface_is_dropped():
    events = build_valid_events(
        raw_events=[_RawEvent(surface="not_a_real_surface")],
        user_id="user-a",
    )
    assert events == []


def test_unknown_event_type_is_dropped():
    events = build_valid_events(
        raw_events=[_RawEvent(event_type="not_a_real_event_type")],
        user_id="user-a",
    )
    assert events == []


def test_one_bad_event_does_not_drop_the_rest_of_the_batch():
    events = build_valid_events(
        raw_events=[
            _RawEvent(surface="garbage"),
            _RawEvent(surface="feed", event_type="click"),
        ],
        user_id="user-a",
    )
    assert len(events) == 1
    assert events[0].event_type == "click"


def test_out_of_range_percentile_is_clamped_not_dropped():
    events = build_valid_events(
        raw_events=[_RawEvent(rank_percentile=-111.4)],
        user_id="user-a",
    )
    assert len(events) == 1
    assert events[0].rank_percentile == 0.0

    events = build_valid_events(
        raw_events=[_RawEvent(rank_percentile=42.0)],
        user_id="user-a",
    )
    assert events[0].rank_percentile == 1.0


def test_unsave_event_type_is_accepted():
    events = build_valid_events(
        raw_events=[_RawEvent(surface="craves", event_type="unsave")],
        user_id="user-a",
    )
    assert len(events) == 1
    assert events[0].event_type == "unsave"


def test_place_detail_surface_is_accepted():
    events = build_valid_events(
        raw_events=[_RawEvent(surface="place_detail", event_type="save")],
        user_id="user-a",
    )
    assert len(events) == 1
    assert events[0].surface == "place_detail"


def test_anonymous_event_has_null_user_id():
    events = build_valid_events(
        raw_events=[_RawEvent()],
        user_id=None,
    )
    assert len(events) == 1
    assert events[0].user_id is None


def test_client_event_id_passes_through_and_is_length_capped():
    events = build_valid_events(
        raw_events=[_RawEvent(client_event_id="z" * 200)],
        user_id="user-a",
    )
    assert len(events[0].client_event_id) == 64


def test_query_and_session_id_are_length_capped():
    events = build_valid_events(
        raw_events=[_RawEvent(query="x" * 500, session_id="y" * 200)],
        user_id="user-a",
    )
    assert len(events[0].query) == 200
    assert len(events[0].session_id) == 64


@pytest.fixture
def db():
    created = {"place_ids": [], "city_ids": [], "event_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
        if created["event_ids"]:
            session.query(RecommendationEvent).filter(
                RecommendationEvent.id.in_(created["event_ids"])
            ).delete(synchronize_session=False)
        if created["place_ids"]:
            session.query(Place).filter(
                Place.id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
        if created["city_ids"]:
            session.query(City).filter(
                City.id.in_(created["city_ids"])
            ).delete(synchronize_session=False)
        session.commit()
        session.close()


def test_record_events_persists_and_returns_accepted_count(db):
    session, created = db
    city = City(
        id=str(uuid.uuid4()), name=f"Ledger Test City {uuid.uuid4().hex[:6]}",
        slug=f"ledger-test-{uuid.uuid4().hex[:8]}", lat=37.8, lng=-122.27, is_active=True,
    )
    session.add(city)
    session.commit()
    created["city_ids"].append(city.id)

    place = Place(name="Ledger Test Place", city_id=city.id, rank_score=0.5)
    session.add(place)
    session.commit()
    created["place_ids"].append(place.id)

    accepted = record_events(
        session,
        raw_events=[
            _RawEvent(surface="feed", event_type="impression", place_id=place.id, position=0),
            _RawEvent(surface="feed", event_type="click", place_id=place.id, position=0),
            _RawEvent(surface="garbage"),  # dropped
        ],
        user_id="user-a",
    )
    assert accepted == 2

    rows = (
        session.query(RecommendationEvent)
        .filter(RecommendationEvent.place_id == place.id)
        .all()
    )
    created["event_ids"].extend([r.id for r in rows])
    assert len(rows) == 2
    assert {r.event_type for r in rows} == {"impression", "click"}


def test_record_events_returns_zero_when_everything_is_invalid(db):
    session, _ = db
    accepted = record_events(
        session,
        raw_events=[_RawEvent(surface="garbage"), _RawEvent(event_type="garbage")],
        user_id="user-a",
    )
    assert accepted == 0


def test_record_events_drops_a_client_event_id_already_persisted(db):
    """
    The core idempotency invariant: a save/unsave outcome resubmitted
    with the same client_event_id (the offline outbox retrying after a
    process-kill-before-persist race -- see cravesStore.ts) must not
    produce a second row, even across two entirely separate
    record_events() calls (not just within one batch).
    """
    session, created = db
    client_event_id = f"dedup-{uuid.uuid4().hex}"

    first = record_events(
        session,
        raw_events=[_RawEvent(surface="feed", event_type="save", client_event_id=client_event_id)],
        user_id="user-a",
    )
    assert first == 1

    second = record_events(
        session,
        raw_events=[_RawEvent(surface="feed", event_type="save", client_event_id=client_event_id)],
        user_id="user-a",
    )
    assert second == 0

    rows = (
        session.query(RecommendationEvent)
        .filter(RecommendationEvent.client_event_id == client_event_id)
        .all()
    )
    created["event_ids"].extend([r.id for r in rows])
    assert len(rows) == 1


def test_record_events_drops_a_duplicate_client_event_id_within_the_same_batch(db):
    session, created = db
    client_event_id = f"dedup-{uuid.uuid4().hex}"

    accepted = record_events(
        session,
        raw_events=[
            _RawEvent(surface="feed", event_type="save", client_event_id=client_event_id),
            _RawEvent(surface="feed", event_type="save", client_event_id=client_event_id),
        ],
        user_id="user-a",
    )
    assert accepted == 1

    rows = (
        session.query(RecommendationEvent)
        .filter(RecommendationEvent.client_event_id == client_event_id)
        .all()
    )
    created["event_ids"].extend([r.id for r in rows])
    assert len(rows) == 1


def test_record_events_with_no_client_event_id_never_dedupes_against_each_other(db):
    # Every impression/click/rank event has client_event_id=None -- must
    # never be treated as "duplicates of each other" by the dedup pass.
    session, created = db
    accepted = record_events(
        session,
        raw_events=[
            _RawEvent(surface="feed", event_type="impression"),
            _RawEvent(surface="feed", event_type="impression"),
        ],
        user_id="user-a",
    )
    assert accepted == 2

    rows = (
        session.query(RecommendationEvent)
        .filter(RecommendationEvent.user_id == "user-a", RecommendationEvent.client_event_id.is_(None))
        .order_by(RecommendationEvent.id.desc())
        .limit(2)
        .all()
    )
    created["event_ids"].extend([r.id for r in rows])


def test_record_rank_outcome_persists_a_rank_event_with_no_percentile(db):
    """
    record_rank_outcome deliberately never sets rank_percentile -- a
    personal ranking's rank_score is a different signal than the
    city-percentile value that field means everywhere else it's set
    (see the function's own docstring). Confirms that stays true even
    though the row otherwise looks just like any other ledger event.
    """
    session, created = db
    city = City(
        id=str(uuid.uuid4()), name=f"Ledger Test City {uuid.uuid4().hex[:6]}",
        slug=f"ledger-test-{uuid.uuid4().hex[:8]}", lat=37.8, lng=-122.27, is_active=True,
    )
    session.add(city)
    session.commit()
    created["city_ids"].append(city.id)

    place = Place(name="Ledger Test Place", city_id=city.id, rank_score=0.5)
    session.add(place)
    session.commit()
    created["place_ids"].append(place.id)

    event = record_rank_outcome(
        session, user_id="user-a", place_id=place.id, city_id=city.id,
    )
    session.commit()
    created["event_ids"].append(event.id)

    row = session.query(RecommendationEvent).filter(RecommendationEvent.id == event.id).one()
    assert row.event_type == "rank"
    assert row.surface == "place_detail"
    assert row.user_id == "user-a"
    assert row.place_id == place.id
    assert row.city_id == city.id
    assert row.rank_percentile is None
