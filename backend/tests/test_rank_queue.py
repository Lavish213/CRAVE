from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_ranking import PlaceRanking
from app.db.models.visit_evidence import VisitEvidence

client = TestClient(app)


def _as_user(user_id: str) -> None:
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
def rank_places(db):
    city_id = str(uuid.uuid4())
    db.add(City(
        id=city_id,
        name="Rank Queue City",
        slug=f"rank-queue-{city_id[:8]}",
        lat=37.0,
        lng=-122.0,
        is_active=True,
    ))
    places = [
        Place(
            id=str(uuid.uuid4()),
            name=f"Queue Place {i}",
            city_id=city_id,
            lat=37.0 + i * 0.001,
            lng=-122.0,
            is_active=True,
            rank_score=0.5,
        )
        for i in range(4)
    ]
    db.add_all(places)
    db.commit()
    yield places
    ids = [p.id for p in places]
    db.query(VisitEvidence).filter(VisitEvidence.place_id.in_(ids)).delete(synchronize_session=False)
    db.query(PlaceRanking).filter(PlaceRanking.place_id.in_(ids)).delete(synchronize_session=False)
    db.query(Place).filter(Place.id.in_(ids)).delete(synchronize_session=False)
    db.query(City).filter(City.id == city_id).delete(synchronize_session=False)
    db.commit()


def _evidence(db, *, user_id: str, place_id: str, tier: str, when: datetime, source: str = "test"):
    row = VisitEvidence(
        user_id=user_id,
        place_id=place_id,
        tier=tier,
        source=source,
        source_ref=str(uuid.uuid4()),
        occurred_at=when,
        confirmed_at=when if tier != "inferred" else None,
        factual_history=True,
        recommendation_influence=True,
    )
    db.add(row)
    db.commit()
    return row


def test_queue_only_includes_declared_and_verified(db, rank_places):
    user_id = f"queue-user-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    _evidence(db, user_id=user_id, place_id=rank_places[0].id, tier="declared", when=now)
    _evidence(db, user_id=user_id, place_id=rank_places[1].id, tier="verified", when=now - timedelta(minutes=1))
    _evidence(db, user_id=user_id, place_id=rank_places[2].id, tier="inferred", when=now - timedelta(minutes=2))

    _as_user(user_id)
    response = client.get("/api/v1/rankings/queue")
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["place_id"] for item in items] == [rank_places[0].id, rank_places[1].id]
    assert {item["evidence_tier"] for item in items} == {"declared", "verified"}


def test_queue_excludes_already_ranked_place(db, rank_places):
    user_id = f"queue-user-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    _evidence(db, user_id=user_id, place_id=rank_places[0].id, tier="declared", when=now)
    db.add(PlaceRanking(
        user_id=user_id,
        place_id=rank_places[0].id,
        tier="liked",
        rank_score=8.0,
        visited_at=now,
    ))
    db.commit()

    _as_user(user_id)
    response = client.get("/api/v1/rankings/queue")
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_queue_deduplicates_multiple_visits_by_place_using_latest(db, rank_places):
    user_id = f"queue-user-{uuid.uuid4()}"
    now = datetime.now(timezone.utc)
    _evidence(db, user_id=user_id, place_id=rank_places[0].id, tier="declared", when=now - timedelta(days=2), source="manual")
    _evidence(db, user_id=user_id, place_id=rank_places[0].id, tier="verified", when=now, source="reservation")

    _as_user(user_id)
    response = client.get("/api/v1/rankings/queue")
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["evidence_tier"] == "verified"
    assert items[0]["evidence_source"] == "reservation"


def test_queue_is_scoped_to_authenticated_user(db, rank_places):
    owner = f"queue-owner-{uuid.uuid4()}"
    other = f"queue-other-{uuid.uuid4()}"
    _evidence(
        db,
        user_id=owner,
        place_id=rank_places[0].id,
        tier="declared",
        when=datetime.now(timezone.utc),
    )

    _as_user(other)
    response = client.get("/api/v1/rankings/queue")
    assert response.status_code == 200
    assert response.json()["items"] == []
