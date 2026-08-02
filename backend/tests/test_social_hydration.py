"""
Coverage for the bulk-hydration added to the social read endpoints.

These endpoints originally returned bare ids (place_id, user_id). A mobile
client rendering a ranked list or a feed then needed one extra request per
row just to turn those ids into a name and a photo — an N+1 paid over the
network, on a phone. Each list endpoint now resolves its references in
bulk server-side.

What's pinned here is the *contract* the client depends on (the enriched
fields are present and correct) and the fact that it stays a bounded
number of queries as the list grows.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_ranking import PlaceRanking
from app.db.models.activity_event import ActivityEvent
from app.db.models.user_follow import UserFollow
from app.db.models.user_profile import UserProfile
from app.services.social import follow_service
from app.services.social.activity_service import record_ranked_place
from app.services.social.leaderboard_service import get_leaderboard

client = TestClient(app)


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(rate_limit, None)


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
    c = City(slug=f"hydration-test-{suffix}", name=f"Hydration City {suffix}")
    db.add(c)
    db.commit()

    yield c

    place_ids = [p.id for p in db.query(Place).filter(Place.city_id == c.id).all()]
    if place_ids:
        db.query(ActivityEvent).filter(ActivityEvent.place_id.in_(place_ids)).delete(
            synchronize_session=False
        )
        db.query(PlaceRanking).filter(PlaceRanking.place_id.in_(place_ids)).delete(
            synchronize_session=False
        )
    db.query(Place).filter(Place.city_id == c.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


@pytest.fixture
def users(db):
    suffix = uuid.uuid4().hex[:8]
    ids = {"alice": f"hyd-alice-{suffix}", "bob": f"hyd-bob-{suffix}"}
    yield ids
    db.query(ActivityEvent).filter(ActivityEvent.user_id.in_(ids.values())).delete(
        synchronize_session=False
    )
    db.query(UserFollow).filter(UserFollow.follower_id.in_(ids.values())).delete(
        synchronize_session=False
    )
    db.query(PlaceRanking).filter(PlaceRanking.user_id.in_(ids.values())).delete(
        synchronize_session=False
    )
    db.query(UserProfile).filter(UserProfile.id.in_(ids.values())).delete(
        synchronize_session=False
    )
    db.commit()


def _make_place(db, city, name=None) -> Place:
    p = Place(name=name or f"Hydration Place {uuid.uuid4().hex[:6]}", city_id=city.id)
    db.add(p)
    db.commit()
    return p


def _rank(db, *, user_id, place_id, score=8.0, tier="liked"):
    r = PlaceRanking(user_id=user_id, place_id=place_id, tier=tier, rank_score=score)
    db.add(r)
    db.commit()
    return r


def _profile(db, user_id, username, display_name=None):
    p = UserProfile(id=user_id, username=username, display_name=display_name)
    db.add(p)
    db.commit()
    return p


# ---------------------------------------------------------------------------
# GET /rankings/me
# ---------------------------------------------------------------------------

def test_my_rankings_include_place_name(db, city, users):
    place = _make_place(db, city, name="Hydrated Diner")
    _rank(db, user_id=users["alice"], place_id=place.id)

    _as_user(users["alice"])
    resp = client.get("/api/v1/rankings/me")

    assert resp.status_code == 200
    rows = resp.json()["rankings"]
    assert len(rows) == 1
    assert rows[0]["place_id"] == place.id
    assert rows[0]["name"] == "Hydrated Diner"
    assert rows[0]["city_id"] == city.id
    # Present in the payload even with no image, so the client can rely on
    # the key existing rather than probing for it.
    assert "primary_image_url" in rows[0]


def test_my_rankings_ordered_highest_score_first(db, city, users):
    low = _make_place(db, city)
    high = _make_place(db, city)
    _rank(db, user_id=users["alice"], place_id=low.id, score=7.0)
    _rank(db, user_id=users["alice"], place_id=high.id, score=9.5)

    _as_user(users["alice"])
    rows = client.get("/api/v1/rankings/me").json()["rankings"]

    assert [r["place_id"] for r in rows] == [high.id, low.id]


def test_my_rankings_empty_list_is_not_an_error(users):
    _as_user(users["alice"])
    resp = client.get("/api/v1/rankings/me")
    assert resp.status_code == 200
    assert resp.json()["rankings"] == []


# ---------------------------------------------------------------------------
# GET /rankings/user/{id} — someone else's list
# ---------------------------------------------------------------------------

def test_public_profile_rankings_are_readable_by_others(db, city, users):
    _profile(db, users["bob"], f"bob{uuid.uuid4().hex[:6]}")
    place = _make_place(db, city, name="Bob's Pick")
    _rank(db, user_id=users["bob"], place_id=place.id)

    _as_user(users["alice"])
    resp = client.get(f"/api/v1/rankings/user/{users['bob']}")

    assert resp.status_code == 200
    assert resp.json()["rankings"][0]["name"] == "Bob's Pick"


def test_private_profile_rankings_are_404(db, city, users):
    profile = _profile(db, users["bob"], f"bob{uuid.uuid4().hex[:6]}")
    profile.is_public = False
    db.commit()

    _as_user(users["alice"])
    assert client.get(f"/api/v1/rankings/user/{users['bob']}").status_code == 404


def test_rankings_for_user_without_profile_is_404(users):
    _as_user(users["alice"])
    assert client.get(f"/api/v1/rankings/user/{users['bob']}").status_code == 404


# ---------------------------------------------------------------------------
# GET /feed/friends
# ---------------------------------------------------------------------------

def test_friends_feed_hydrates_actor_and_place(db, city, users):
    _profile(db, users["bob"], f"bob{uuid.uuid4().hex[:6]}", display_name="Bob R")
    place = _make_place(db, city, name="Feed Cafe")
    record_ranked_place(db, user_id=users["bob"], place_id=place.id, tier="liked", score=9.0)
    db.commit()

    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])

    _as_user(users["alice"])
    events = client.get("/api/v1/feed/friends").json()["events"]

    assert len(events) == 1
    assert events[0]["place_name"] == "Feed Cafe"
    assert events[0]["actor"]["display_name"] == "Bob R"
    assert events[0]["payload"] == {"tier": "liked", "score": 9.0}


def test_friends_feed_actor_without_profile_still_renders(db, city, users):
    """A user can rank things before claiming a username — the feed must
    degrade to a placeholder rather than dropping the row or 500ing."""
    place = _make_place(db, city)
    record_ranked_place(db, user_id=users["bob"], place_id=place.id, tier="fine", score=5.0)
    db.commit()
    follow_service.follow_user(db, follower_id=users["alice"], followee_id=users["bob"])

    _as_user(users["alice"])
    events = client.get("/api/v1/feed/friends").json()["events"]

    assert len(events) == 1
    assert events[0]["actor"]["id"] == users["bob"]
    assert events[0]["actor"]["username"] is None


def test_friends_feed_empty_short_circuits(users):
    _as_user(users["alice"])
    resp = client.get("/api/v1/feed/friends")
    assert resp.status_code == 200
    assert resp.json()["events"] == []


# ---------------------------------------------------------------------------
# Leaderboard
# ---------------------------------------------------------------------------

def test_leaderboard_includes_usernames(db, city, users):
    _profile(db, users["alice"], f"alice{uuid.uuid4().hex[:6]}", display_name="Alice A")
    place = _make_place(db, city)
    _rank(db, user_id=users["alice"], place_id=place.id)

    rows = get_leaderboard(db, user_id=users["alice"], among="global", limit=100)
    mine = next(r for r in rows if r["user_id"] == users["alice"])

    assert mine["display_name"] == "Alice A"
    assert mine["username"] is not None
    assert mine["places_logged"] == 1


def test_leaderboard_user_without_profile_has_null_username(db, city, users):
    place = _make_place(db, city)
    _rank(db, user_id=users["bob"], place_id=place.id)

    rows = get_leaderboard(db, user_id=users["bob"], among="global", limit=100)
    theirs = next(r for r in rows if r["user_id"] == users["bob"])

    assert theirs["username"] is None
    assert theirs["places_logged"] == 1
