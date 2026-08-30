from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import rate_limit
from app.db.models.city import City
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.main import app
from app.services.cache.response_cache import response_cache


client = TestClient(app)


@pytest.fixture(autouse=True)
def _route_overrides_and_cache():
    app.dependency_overrides[rate_limit] = lambda: None
    response_cache.delete_prefix("feed-snapshot:")
    yield
    response_cache.delete_prefix("feed-snapshot:")
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture
def seeded_city():
    db = SessionLocal()
    city = City(
        id=str(uuid.uuid4()),
        name="Cursor Test City",
        slug=f"cursor-test-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(city)
    db.commit()

    place_ids: list[str] = []
    for index, score in enumerate((0.50, 0.45, 0.40, 0.35, 0.30)):
        place = Place(
            id=str(uuid.uuid4()),
            name=f"Cursor Place {index}",
            city_id=city.id,
            rank_score=score,
            is_active=True,
        )
        place_ids.append(place.id)
        db.add(place)
    db.commit()

    try:
        yield db, city, place_ids
    finally:
        db.query(Place).filter(Place.city_id == city.id).delete(synchronize_session=False)
        db.query(City).filter(City.id == city.id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_cursor_snapshot_does_not_shift_when_a_new_place_is_inserted(seeded_city):
    db, city, original_ids = seeded_city

    first = client.get(
        "/api/v1/places/feed",
        params={"city_id": city.id, "page_size": 2},
    )
    assert first.status_code == 200
    first_body = first.json()
    first_ids = [item["id"] for item in first_body["items"]]
    assert len(first_ids) == 2
    assert first_body["next_cursor"]

    inserted = Place(
        id=str(uuid.uuid4()),
        name="Inserted After Page One",
        city_id=city.id,
        rank_score=0.99,
        is_active=True,
    )
    db.add(inserted)
    db.commit()

    second = client.get(
        "/api/v1/places/feed",
        params={
            "city_id": city.id,
            "page_size": 2,
            "cursor": first_body["next_cursor"],
        },
    )
    assert second.status_code == 200
    second_body = second.json()
    second_ids = [item["id"] for item in second_body["items"]]

    assert set(first_ids).isdisjoint(second_ids)
    assert inserted.id not in second_ids
    assert set(second_ids).issubset(set(original_ids))
    assert second_body["next_cursor"] != first_body["next_cursor"]


def test_cursor_cannot_be_reused_for_a_different_feed_scope(seeded_city):
    _db, city, _original_ids = seeded_city
    first = client.get(
        "/api/v1/places/feed",
        params={"city_id": city.id, "page_size": 2},
    )
    cursor = first.json()["next_cursor"]

    mismatched = client.get(
        "/api/v1/places/feed",
        params={"city_id": str(uuid.uuid4()), "page_size": 2, "cursor": cursor},
    )

    assert mismatched.status_code == 400
    assert mismatched.json()["detail"] == "Cursor does not match this feed"


def test_unknown_cursor_returns_explicit_expired_response(seeded_city):
    _db, city, _original_ids = seeded_city

    response = client.get(
        "/api/v1/places/feed",
        params={"city_id": city.id, "page_size": 2, "cursor": "missing.2"},
    )

    assert response.status_code == 410
    assert response.json()["detail"] == "Feed cursor expired; refresh the feed"
