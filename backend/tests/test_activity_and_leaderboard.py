"""
Coverage for app.services.social.activity_service (the friend feed's
writer/reader) and app.services.social.leaderboard_service (ranked by
places-logged count, Beli's actual leaderboard metric — not average
score). Both are thin layers on top of the follow graph and ranking
engine, which is where the real complexity already lives and is tested.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_ranking import PlaceRanking
from app.db.models.activity_event import ActivityEvent
from app.db.models.user_follow import UserFollow
from app.services.social import follow_service
from app.services.social.activity_service import (
    record_ranked_place,
    record_followed_user,
    list_friend_feed,
)
from app.services.social.leaderboard_service import get_leaderboard, LeaderboardError


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
    c = City(slug=f"activity-test-{suffix}", name=f"Activity Test City {suffix}")
    db.add(c)
    db.commit()

    yield c

    db.query(ActivityEvent).filter(
        ActivityEvent.place_id.in_(db.query(Place.id).filter(Place.city_id == c.id))
    ).delete(synchronize_session=False)
    db.query(PlaceRanking).filter(
        PlaceRanking.place_id.in_(db.query(Place.id).filter(Place.city_id == c.id))
    ).delete(synchronize_session=False)
    db.query(Place).filter(Place.city_id == c.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


@pytest.fixture
def users():
    suffix = uuid.uuid4().hex[:8]
    ids = {
        "alice": f"act-test-alice-{suffix}",
        "bob": f"act-test-bob-{suffix}",
        "carol": f"act-test-carol-{suffix}",
    }
    yield ids
    with SessionLocal() as cleanup_db:
        cleanup_db.query(ActivityEvent).filter(
            ActivityEvent.user_id.in_(ids.values())
        ).delete(synchronize_session=False)
        cleanup_db.query(UserFollow).filter(
            UserFollow.follower_id.in_(ids.values())
        ).delete(synchronize_session=False)
        cleanup_db.commit()


def _make_place(db, city, score_seed=1.0):
    p = Place(name=f"Activity Test Place {uuid.uuid4().hex[:6]}", city_id=city.id)
    db.add(p)
    db.commit()
    return p


# ---------------------------------------------------------------------------
# Activity feed
# ---------------------------------------------------------------------------

def test_record_ranked_place_creates_event(db, city, users):
    place = _make_place(db, city)
    event = record_ranked_place(
        db, user_id=users["alice"], place_id=place.id, tier="liked", score=8.5,
    )
    db.commit()
    assert event.event_type == "ranked_place"
    assert event.payload == {"tier": "liked", "score": 8.5}


def test_record_followed_user_creates_event(db, users):
    event = record_followed_user(db, user_id=users["alice"], target_user_id=users["bob"])
    db.commit()
    assert event.event_type == "followed_user"
    assert event.target_user_id == users["bob"]


def test_friend_feed_only_shows_followed_users(db, city, users):
    place = _make_place(db, city)
    record_ranked_place(db, user_id=users["bob"], place_id=place.id, tier="liked", score=8.0)
    record_ranked_place(db, user_id=users["carol"], place_id=place.id, tier="fine", score=5.0)
    db.commit()

    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])

    feed = list_friend_feed(db, follower_ids=follow_service.list_following(db, users["alice"]))
    actors = {e.user_id for e in feed}
    assert actors == {users["bob"]}


def test_friend_feed_empty_with_no_follows(db, users):
    assert list_friend_feed(db, follower_ids=[]) == []


def test_friend_feed_newest_first(db, city, users):
    place = _make_place(db, city)
    first = record_ranked_place(db, user_id=users["bob"], place_id=place.id, tier="liked", score=8.0)
    db.commit()

    place2 = _make_place(db, city)
    second = record_ranked_place(db, user_id=users["bob"], place_id=place2.id, tier="fine", score=5.0)
    db.commit()

    feed = list_friend_feed(db, follower_ids=[users["bob"]])
    assert feed[0].id == second.id
    assert feed[1].id == first.id


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

def _seed_ranking(db, *, user_id, place_id, tier="liked", score=5.0):
    r = PlaceRanking(user_id=user_id, place_id=place_id, tier=tier, rank_score=score)
    db.add(r)
    db.commit()
    return r


def test_leaderboard_orders_by_places_logged_count(db, city, users):
    places = [_make_place(db, city) for _ in range(3)]
    _seed_ranking(db, user_id=users["alice"], place_id=places[0].id)
    _seed_ranking(db, user_id=users["alice"], place_id=places[1].id)
    _seed_ranking(db, user_id=users["alice"], place_id=places[2].id)
    _seed_ranking(db, user_id=users["bob"], place_id=places[0].id)

    rows = get_leaderboard(db, user_id=users["alice"], among="global", limit=100)
    by_user = {r["user_id"]: r["places_logged"] for r in rows}
    assert by_user[users["alice"]] == 3
    assert by_user[users["bob"]] == 1
    # alice logged more, so alice must rank above bob.
    ranks = {r["user_id"]: r["rank"] for r in rows}
    assert ranks[users["alice"]] < ranks[users["bob"]]


def test_leaderboard_scoped_to_city(db, city, users):
    suffix = uuid.uuid4().hex[:8]
    other_city = City(slug=f"other-activity-test-{suffix}", name=f"Other City {suffix}")
    db.add(other_city)
    db.commit()

    in_city_place = _make_place(db, city)
    other_city_place = Place(name=f"Other Place {suffix}", city_id=other_city.id)
    db.add(other_city_place)
    db.commit()

    _seed_ranking(db, user_id=users["alice"], place_id=in_city_place.id)
    _seed_ranking(db, user_id=users["bob"], place_id=other_city_place.id)

    rows = get_leaderboard(db, user_id=users["alice"], among="global", city_slug=city.slug)
    user_ids = {r["user_id"] for r in rows}
    assert users["alice"] in user_ids
    assert users["bob"] not in user_ids

    db.query(Place).filter(Place.city_id == other_city.id).delete()
    db.query(City).filter(City.id == other_city.id).delete()
    db.commit()


def test_leaderboard_friends_scope_excludes_non_followed(db, city, users):
    places = [_make_place(db, city) for _ in range(2)]
    _seed_ranking(db, user_id=users["alice"], place_id=places[0].id)
    _seed_ranking(db, user_id=users["bob"], place_id=places[1].id)
    _seed_ranking(db, user_id=users["carol"], place_id=places[1].id)

    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])

    rows = get_leaderboard(db, user_id=users["alice"], among="friends")
    user_ids = {r["user_id"] for r in rows}
    assert users["alice"] in user_ids  # self always included
    assert users["bob"] in user_ids  # followed
    assert users["carol"] not in user_ids  # not followed


def test_leaderboard_unknown_city_slug_raises(db, users):
    with pytest.raises(LeaderboardError):
        get_leaderboard(db, user_id=users["alice"], city_slug="does-not-exist-anywhere")


def test_leaderboard_invalid_among_raises(db, users):
    with pytest.raises(LeaderboardError):
        get_leaderboard(db, user_id=users["alice"], among="nonsense")
