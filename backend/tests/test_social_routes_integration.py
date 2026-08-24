"""
End-to-end HTTP coverage for the new profile/follow/ranking/feed/
leaderboard routes — confirms actual wiring (registration, request/
response shapes, auth plumbing), not just the service-layer logic
already covered in test_profile_service.py, test_follow_service.py,
test_ranking_service.py, and test_activity_and_leaderboard.py.

get_current_user_id resolves to a fixed "dev-user" id when no Supabase
JWT secret is configured (see app.core.user_auth) — dependency_overrides
is used here to simulate distinct users through the actual HTTP layer,
since a follow graph and a leaderboard are meaningless with only one
possible caller identity.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.user_auth import get_current_user_id
from app.core.rate_limit import rate_limit
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.user_profile import UserProfile
from app.db.models.user_follow import UserFollow
from app.db.models.place_ranking import PlaceRanking
from app.db.models.activity_event import ActivityEvent

client = TestClient(app)


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _clear_overrides():
    # Every route test file that shares this process's TestClient also
    # shares rate_limit's in-memory, per-process, per-IP bucket (60 req/60s
    # — see app.core.rate_limit). A fast full-suite run puts every
    # TestClient-based test file's requests in the same window, so this
    # file's ~15 requests would otherwise eat into unrelated tests' budget
    # (and vice versa) — bypassed here, scoped to just this file's tests.
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
    c = City(slug=f"route-test-{suffix}", name=f"Route Test City {suffix}")
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
def users(db):
    suffix = uuid.uuid4().hex[:8]
    ids = {
        "alice": f"route-test-alice-{suffix}",
        "bob": f"route-test-bob-{suffix}",
    }
    yield ids
    db.query(ActivityEvent).filter(ActivityEvent.user_id.in_(ids.values())).delete(
        synchronize_session=False
    )
    db.query(UserFollow).filter(UserFollow.follower_id.in_(ids.values())).delete(
        synchronize_session=False
    )
    db.query(UserProfile).filter(UserProfile.id.in_(ids.values())).delete(
        synchronize_session=False
    )
    db.commit()


def test_profile_setup_and_fetch(users):
    _as_user(users["alice"])
    resp = client.post("/api/v1/profile/setup", json={"username": f"user_{uuid.uuid4().hex[:8]}"})
    assert resp.status_code == 201

    resp = client.get("/api/v1/profile/me")
    assert resp.status_code == 200
    assert resp.json()["id"] == users["alice"]


def test_profile_setup_duplicate_username_conflicts(users):
    username = f"dup_{uuid.uuid4().hex[:8]}"

    _as_user(users["alice"])
    resp = client.post("/api/v1/profile/setup", json={"username": username})
    assert resp.status_code == 201

    _as_user(users["bob"])
    resp = client.post("/api/v1/profile/setup", json={"username": username})
    assert resp.status_code == 409


def test_follow_unfollow_roundtrip(users):
    _as_user(users["alice"])
    resp = client.post(f"/api/v1/follows/{users['bob']}")
    assert resp.status_code == 201

    resp = client.get(f"/api/v1/follows/status/{users['bob']}")
    assert resp.status_code == 200
    assert resp.json()["following"] is True

    resp = client.get("/api/v1/follows/following")
    assert resp.json()["user_ids"] == [users["bob"]]

    resp = client.delete(f"/api/v1/follows/{users['bob']}")
    assert resp.status_code == 200

    resp = client.get(f"/api/v1/follows/status/{users['bob']}")
    assert resp.json()["following"] is False


def test_repeated_follow_does_not_duplicate_the_activity_event(users, db):
    # Simulates a client retry after a lost response: the follow already
    # succeeded server-side, but the client (never having seen that) POSTs
    # the same follow again. That must not duplicate "so-and-so followed
    # you" in the followee's activity feed.
    _as_user(users["alice"])
    resp = client.post(f"/api/v1/follows/{users['bob']}")
    assert resp.status_code == 201

    resp = client.post(f"/api/v1/follows/{users['bob']}")
    assert resp.status_code == 201

    count = (
        db.query(ActivityEvent)
        .filter(
            ActivityEvent.user_id == users["alice"],
            ActivityEvent.event_type == "followed_user",
        )
        .count()
    )
    assert count == 1


def test_cannot_follow_self_via_route(users):
    _as_user(users["alice"])
    resp = client.post(f"/api/v1/follows/{users['alice']}")
    assert resp.status_code == 400


def test_start_ranking_first_in_tier_returns_ranked_immediately(city):
    place = Place(name=f"Route Test Place {uuid.uuid4().hex[:6]}", city_id=city.id)
    with SessionLocal() as setup_db:
        setup_db.add(place)
        setup_db.commit()
        setup_db.refresh(place)

    _as_user(f"route-test-ranker-{uuid.uuid4().hex[:8]}")
    resp = client.post("/api/v1/rankings", json={"place_id": place.id, "tier": "liked"})
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "ranked"
    assert 6.6 <= body["ranking"]["rank_score"] <= 10.0


def test_ranking_unknown_place_returns_400(users):
    _as_user(users["alice"])
    resp = client.post("/api/v1/rankings", json={"place_id": "does-not-exist", "tier": "liked"})
    assert resp.status_code == 400


def test_leaderboard_endpoint_reachable(users):
    _as_user(users["alice"])
    resp = client.get("/api/v1/leaderboard")
    assert resp.status_code == 200
    assert "leaderboard" in resp.json()


def test_friends_feed_endpoint_reachable(users):
    _as_user(users["alice"])
    resp = client.get("/api/v1/feed/friends")
    assert resp.status_code == 200
    assert resp.json()["events"] == []


def test_username_available_endpoint():
    resp = client.get("/api/v1/profile/username-available", params={"username": "totally_new_name_xyz"})
    assert resp.status_code == 200
    assert resp.json()["available"] is True
