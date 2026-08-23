"""
Coverage for get_friend_rankings_for_place — "which of my friends ranked
this place," the direct equivalent of Beli's friend-rating feature.
CRAVE already had all the underlying data (PlaceRanking + the follow
graph) but never surfaced it anywhere.
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
from app.db.models.place_ranking import PlaceRanking
from app.db.models.user_profile import UserProfile
from app.db.models.user_follow import UserFollow
from app.services.social.friend_rankings_service import get_friend_rankings_for_place


@pytest.fixture
def db():
    # Created-row cleanup matters here specifically: an uncleaned Place
    # row (rank_score defaults to 0.0, zero images) is exactly the shape
    # ImageWorker's starvation-reserve logic (test_image_worker_starvation.py)
    # deliberately goes looking for in its own *unscoped* query — confirmed
    # live via full-suite runs that leaving one behind here made that
    # unrelated test flake depending on file run order.
    created = {"place_ids": [], "city_ids": [], "user_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
        if created["place_ids"]:
            session.query(PlaceRanking).filter(
                PlaceRanking.place_id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
            session.query(Place).filter(
                Place.id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
        if created["user_ids"]:
            session.query(UserFollow).filter(
                UserFollow.follower_id.in_(created["user_ids"])
                | UserFollow.followee_id.in_(created["user_ids"])
            ).delete(synchronize_session=False)
            session.query(UserProfile).filter(
                UserProfile.id.in_(created["user_ids"])
            ).delete(synchronize_session=False)
        if created["city_ids"]:
            session.query(City).filter(
                City.id.in_(created["city_ids"])
            ).delete(synchronize_session=False)
        session.commit()
        session.close()


def _make_user(db, created, *, username: str) -> UserProfile:
    profile = UserProfile(id=str(uuid.uuid4()), username=username, display_name=username.title())
    db.add(profile)
    db.commit()
    created["user_ids"].append(profile.id)
    return profile


def _make_place(db, created) -> Place:
    city = City(
        id=str(uuid.uuid4()), name="Friend Rankings Test City",
        slug=f"friend-rankings-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    created["city_ids"].append(city.id)
    place = Place(name="Friend Rankings Test Place", city_id=city.id, lat=37.8, lng=-122.27)
    db.add(place)
    db.commit()
    created["place_ids"].append(place.id)
    return place


def _rank(db, *, user: UserProfile, place: Place, tier: str, score: float) -> None:
    db.add(PlaceRanking(user_id=user.id, place_id=place.id, tier=tier, rank_score=score))
    db.commit()


def _follow(db, *, follower: UserProfile, followee: UserProfile) -> None:
    db.add(UserFollow(follower_id=follower.id, followee_id=followee.id))
    db.commit()


def test_returns_rankings_from_followed_users_ordered_best_first(db):
    session, created = db
    me = _make_user(session, created, username=f"me_{uuid.uuid4().hex[:8]}")
    friend_a = _make_user(session, created, username=f"friend_a_{uuid.uuid4().hex[:8]}")
    friend_b = _make_user(session, created, username=f"friend_b_{uuid.uuid4().hex[:8]}")
    place = _make_place(session, created)

    _follow(session, follower=me, followee=friend_a)
    _follow(session, follower=me, followee=friend_b)
    _rank(session, user=friend_a, place=place, tier="liked", score=8.0)
    _rank(session, user=friend_b, place=place, tier="liked", score=9.5)

    result = get_friend_rankings_for_place(session, place_id=place.id, user_id=me.id)

    assert [r["username"] for r in result] == [friend_b.username, friend_a.username]
    assert result[0]["rank_score"] == 9.5
    assert result[0]["tier"] == "liked"


def test_excludes_rankings_from_users_not_followed(db):
    session, created = db
    me = _make_user(session, created, username=f"me_{uuid.uuid4().hex[:8]}")
    stranger = _make_user(session, created, username=f"stranger_{uuid.uuid4().hex[:8]}")
    place = _make_place(session, created)

    _rank(session, user=stranger, place=place, tier="liked", score=9.0)

    result = get_friend_rankings_for_place(session, place_id=place.id, user_id=me.id)

    assert result == []


def test_returns_empty_list_when_following_nobody(db):
    session, created = db
    me = _make_user(session, created, username=f"me_{uuid.uuid4().hex[:8]}")
    place = _make_place(session, created)

    result = get_friend_rankings_for_place(session, place_id=place.id, user_id=me.id)

    assert result == []


def test_excludes_followed_users_who_have_not_ranked_this_place(db):
    session, created = db
    me = _make_user(session, created, username=f"me_{uuid.uuid4().hex[:8]}")
    friend = _make_user(session, created, username=f"friend_{uuid.uuid4().hex[:8]}")
    place = _make_place(session, created)

    _follow(session, follower=me, followee=friend)
    # friend never ranks the place

    result = get_friend_rankings_for_place(session, place_id=place.id, user_id=me.id)

    assert result == []
