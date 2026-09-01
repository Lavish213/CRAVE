"""
Coverage for E3's "has video" card signal: get_has_video_bulk() and its
wiring into PlaceOut / PlaceCardOut (Feed, Search, Map). See
docs/E2_E3_E10_PRODUCT_TRADEOFFS_2026-08-31.md.

Two things worth a real regression test:
  1. The visibility gate itself -- only status=approved AND
     moderation_status=approved videos count, mirroring the same two
     gates the feed already uses for what's actually shown.
  2. PlaceOut/PlaceCardOut's `_inject_category` validator rebuilds a
     fresh dict from an ORM object rather than passing it through --
     any field not explicitly named in that dict-building code is
     silently dropped even if set as an attribute before validation.
     `has_video` needed a change there specifically for this reason;
     this is the test that would have caught it being missed.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_video import (
    PlaceVideo,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    MOD_APPROVED,
    MOD_PENDING_REVIEW,
)
from app.services.query.place_video_visibility_query import get_has_video_bulk
from app.api.v1.schemas.places import PlaceOut
from app.api.v1.schemas.place_card import PlaceCardOut


@pytest.fixture
def db():
    created = {"place_ids": [], "city_ids": [], "video_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
        if created["video_ids"]:
            session.query(PlaceVideo).filter(
                PlaceVideo.id.in_(created["video_ids"])
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


def _make_place(session, created) -> Place:
    city_id = str(uuid.uuid4())
    session.add(City(
        id=city_id, name="Video Presence Test City",
        slug=f"video-presence-{uuid.uuid4().hex[:8]}",
        lat=37.0, lng=-122.0, is_active=True,
    ))
    place = Place(
        id=str(uuid.uuid4()), name="Video Presence Test Place", city_id=city_id,
        lat=37.0, lng=-122.0, is_active=True, rank_score=0.5,
    )
    session.add(place)
    session.commit()
    created["city_ids"].append(city_id)
    created["place_ids"].append(place.id)
    return place


def _make_video(session, created, *, place: Place, status: str, moderation_status: str) -> PlaceVideo:
    video = PlaceVideo(
        id=str(uuid.uuid4()),
        place_id=place.id,
        uploaded_by=f"user-{uuid.uuid4().hex[:8]}",
        status=status,
        moderation_status=moderation_status,
    )
    session.add(video)
    session.commit()
    created["video_ids"].append(video.id)
    return video


def test_approved_and_visible_video_counts(db):
    session, created = db
    place = _make_place(session, created)
    _make_video(session, created, place=place, status=STATUS_APPROVED, moderation_status=MOD_APPROVED)

    result = get_has_video_bulk(session, place_ids=[place.id])
    assert result.get(place.id) is True


def test_pending_pipeline_video_does_not_count(db):
    session, created = db
    place = _make_place(session, created)
    _make_video(session, created, place=place, status=STATUS_PENDING, moderation_status=MOD_APPROVED)

    result = get_has_video_bulk(session, place_ids=[place.id])
    assert result.get(place.id, False) is False


def test_rejected_video_does_not_count(db):
    session, created = db
    place = _make_place(session, created)
    _make_video(session, created, place=place, status=STATUS_REJECTED, moderation_status=MOD_APPROVED)

    result = get_has_video_bulk(session, place_ids=[place.id])
    assert result.get(place.id, False) is False


def test_pipeline_approved_but_moderation_pending_does_not_count(db):
    """
    A video can pass the processing pipeline cleanly (status=approved)
    and still be pulled from view by moderation without touching that
    pipeline outcome -- see PlaceVideo's own moderation_status comment.
    Both gates must hold, not just one.
    """
    session, created = db
    place = _make_place(session, created)
    _make_video(session, created, place=place, status=STATUS_APPROVED, moderation_status=MOD_PENDING_REVIEW)

    result = get_has_video_bulk(session, place_ids=[place.id])
    assert result.get(place.id, False) is False


def test_place_with_no_video_is_absent_from_result(db):
    session, created = db
    place = _make_place(session, created)

    result = get_has_video_bulk(session, place_ids=[place.id])
    assert place.id not in result


def test_empty_place_ids_short_circuits(db):
    session, _created = db
    assert get_has_video_bulk(session, place_ids=[]) == {}


def test_place_out_surfaces_has_video_set_on_orm_object(db):
    """
    Regression guard for PlaceOut's ORM-object model_validator branch,
    which rebuilds an explicit dict rather than passing the object
    through -- has_video must be named there or it's silently dropped
    even though it's a real attribute on the instance.
    """
    session, created = db
    place = _make_place(session, created)
    place.has_video = True
    out = PlaceOut.model_validate(place, from_attributes=True)
    assert out.has_video is True


def test_place_card_out_surfaces_has_video_set_on_orm_object(db):
    session, created = db
    place = _make_place(session, created)
    place.has_video = True
    out = PlaceCardOut.model_validate(place, from_attributes=True)
    assert out.has_video is True


def test_place_out_defaults_has_video_false_when_unset(db):
    session, created = db
    place = _make_place(session, created)
    out = PlaceOut.model_validate(place, from_attributes=True)
    assert out.has_video is False
