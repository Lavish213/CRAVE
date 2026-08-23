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
from app.db.models.user_block import UserBlock
from app.services.social import block_service, follow_service
from app.services.social.activity_service import (
    record_ranked_place,
    record_followed_user,
    list_friend_feed,
)
from app.services.social.leaderboard_service import get_leaderboard, LeaderboardError
from app.services.cache.response_cache import response_cache
from app.services.cache.cache_keys import leaderboard_global_base_key

# Cross-test leaderboard cache isolation is handled suite-wide by
# tests/conftest.py's autouse _clear_leaderboard_cache fixture.


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
        cleanup_db.query(UserBlock).filter(
            UserBlock.blocker_id.in_(ids.values())
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


def test_leaderboard_global_scope_excludes_blocked_users(db, city, users):
    """Global scope has no follow-graph filtering to inherit block-safety
    from (unlike 'friends'), so it needs its own exclusion — a blocked
    user's name/avatar must not surface here even though every other
    surface (profile, friends feed) already hides them."""
    places = [_make_place(db, city) for _ in range(2)]
    _seed_ranking(db, user_id=users["alice"], place_id=places[0].id)
    _seed_ranking(db, user_id=users["bob"], place_id=places[1].id)
    _seed_ranking(db, user_id=users["carol"], place_id=places[1].id)

    block_service.block_user(db, blocker_id=users["alice"], blocked_id=users["bob"])

    rows = get_leaderboard(db, user_id=users["alice"], among="global", limit=100)
    user_ids = {r["user_id"] for r in rows}
    assert users["alice"] in user_ids
    assert users["carol"] in user_ids
    assert users["bob"] not in user_ids


def test_leaderboard_global_scope_excludes_users_who_blocked_you(db, city, users):
    places = [_make_place(db, city) for _ in range(2)]
    _seed_ranking(db, user_id=users["alice"], place_id=places[0].id)
    _seed_ranking(db, user_id=users["bob"], place_id=places[1].id)

    # bob blocked alice, not the other way around — still must be mutual.
    block_service.block_user(db, blocker_id=users["bob"], blocked_id=users["alice"])

    rows = get_leaderboard(db, user_id=users["alice"], among="global", limit=100)
    user_ids = {r["user_id"] for r in rows}
    assert users["bob"] not in user_ids


def test_leaderboard_unknown_city_slug_raises(db, users):
    with pytest.raises(LeaderboardError):
        get_leaderboard(db, user_id=users["alice"], city_slug="does-not-exist-anywhere")


def test_leaderboard_invalid_among_raises(db, users):
    with pytest.raises(LeaderboardError):
        get_leaderboard(db, user_id=users["alice"], among="nonsense")


# ---------------------------------------------------------------------------
# Leaderboard caching — the global scope's base ranking is now cached
# (previously recomputed a full GROUP BY/COUNT/ORDER BY aggregate on every
# request, with no caching at all).
# ---------------------------------------------------------------------------

def test_leaderboard_global_scope_reads_from_cache_when_present(db, users):
    # Planted directly, bypassing the DB entirely -- these counts don't
    # correspond to anything real for these fresh, zero-ranking uuid
    # users. The only way they can appear in the result is if
    # get_leaderboard actually read this cached base instead of
    # recomputing from PlaceRanking.
    fake_base = [
        {"user_id": users["alice"], "places_logged": 999, "username": "alice",
         "display_name": None, "avatar_url": None},
        {"user_id": users["bob"], "places_logged": 1, "username": "bob",
         "display_name": None, "avatar_url": None},
    ]
    response_cache.set(leaderboard_global_base_key(city_slug=None), fake_base, 60)

    rows = get_leaderboard(db, user_id=users["carol"], among="global", limit=100)
    by_user = {r["user_id"]: r["places_logged"] for r in rows}
    assert by_user[users["alice"]] == 999
    assert by_user[users["bob"]] == 1


def test_leaderboard_global_scope_filters_cached_base_per_viewer(db, users):
    # Same idea, but proves block-filtering is applied *after* the cache
    # read, per viewer -- not baked into the cached value itself (which
    # would either leak across viewers or force disabling the cache).
    fake_base = [
        {"user_id": users["alice"], "places_logged": 5, "username": "alice",
         "display_name": None, "avatar_url": None},
        {"user_id": users["bob"], "places_logged": 3, "username": "bob",
         "display_name": None, "avatar_url": None},
    ]
    response_cache.set(leaderboard_global_base_key(city_slug=None), fake_base, 60)
    block_service.block_user(db, blocker_id=users["carol"], blocked_id=users["bob"])

    carol_rows = get_leaderboard(db, user_id=users["carol"], among="global", limit=100)
    carol_ids = {r["user_id"] for r in carol_rows}
    assert users["alice"] in carol_ids
    assert users["bob"] not in carol_ids

    # A different viewer, no block of their own, reads the exact same
    # cached pool and still sees bob -- proving the filter is per-viewer,
    # not baked into what's cached.
    alice_rows = get_leaderboard(db, user_id=users["alice"], among="global", limit=100)
    alice_ids = {r["user_id"] for r in alice_rows}
    assert users["bob"] in alice_ids
