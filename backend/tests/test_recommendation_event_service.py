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


def test_anonymous_event_has_null_user_id():
    events = build_valid_events(
        raw_events=[_RawEvent()],
        user_id=None,
    )
    assert len(events) == 1
    assert events[0].user_id is None


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
