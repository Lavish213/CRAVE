from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.models.city import City
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.main import app


client = TestClient(app)


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(rate_limit, None)
    app.dependency_overrides.pop(get_current_user_id, None)


@pytest.fixture()
def db():
    session = SessionLocal()
    session._craves_data_test_city_ids = []  # type: ignore[attr-defined]
    session._craves_data_test_place_ids = []  # type: ignore[attr-defined]
    try:
        yield session
    finally:
        city_ids = getattr(session, "_craves_data_test_city_ids", [])
        place_ids = getattr(session, "_craves_data_test_place_ids", [])
        if place_ids or city_ids:
            from app.db.models.crave_collection import CraveCollection, CraveCollectionPlace
            from app.db.models.crave_place_state import CravePlaceState
            from app.db.models.crave_tag import CravePlaceTag, CraveTag

            session.rollback()
            state_ids = [
                row[0]
                for row in session.query(CravePlaceState.id)
                .filter(CravePlaceState.place_id.in_(place_ids))
                .all()
            ]
            if state_ids:
                session.query(CraveCollectionPlace).filter(
                    CraveCollectionPlace.state_id.in_(state_ids)
                ).delete(synchronize_session=False)
                session.query(CravePlaceTag).filter(
                    CravePlaceTag.state_id.in_(state_ids)
                ).delete(synchronize_session=False)
                session.query(CravePlaceState).filter(
                    CravePlaceState.id.in_(state_ids)
                ).delete(synchronize_session=False)
            session.query(CraveCollection).filter(
                CraveCollection.user_id.like("user-%")
            ).delete(synchronize_session=False)
            session.query(CraveTag).filter(
                CraveTag.user_id.like("user-%")
            ).delete(synchronize_session=False)
            if place_ids:
                session.query(Place).filter(Place.id.in_(place_ids)).delete(synchronize_session=False)
            if city_ids:
                session.query(City).filter(City.id.in_(city_ids)).delete(synchronize_session=False)
            session.commit()
        session.close()


def _make_place(db) -> Place:
    city_id = str(uuid.uuid4())
    city = City(
        id=city_id,
        name="Craves Data City",
        slug=f"craves-data-{city_id[:8]}",
        lat=37.8,
        lng=-122.27,
        is_active=True,
    )
    place = Place(
        id=str(uuid.uuid4()),
        name="Craves Data Place",
        city_id=city_id,
        lat=37.8,
        lng=-122.27,
        is_active=True,
    )
    db.add(city)
    db.add(place)
    db.commit()
    db._craves_data_test_city_ids.append(city.id)
    db._craves_data_test_place_ids.append(place.id)
    return place


def test_collections_and_tags_are_user_scoped(db):
    user_a = f"user-{uuid.uuid4()}"
    user_b = f"user-{uuid.uuid4()}"

    _as_user(user_a)
    collection = client.post("/api/v1/craves/collections", json={"name": "Date night"})
    tag = client.post("/api/v1/craves/tags", json={"name": "Ramen", "color": "gold"})
    assert collection.status_code == 201
    assert tag.status_code == 201

    _as_user(user_b)
    assert client.get("/api/v1/craves/collections").json() == []
    assert client.get("/api/v1/craves/tags").json() == []

    _as_user(user_a)
    assert client.get("/api/v1/craves/collections").json()[0]["name"] == "Date night"
    assert client.get("/api/v1/craves/tags").json()[0]["name"] == "Ramen"


def test_upsert_place_state_records_status_notes_dishes_collections_and_tags(db):
    user_id = f"user-{uuid.uuid4()}"
    _as_user(user_id)
    place = _make_place(db)
    collection_id = client.post(
        "/api/v1/craves/collections",
        json={"name": "Oakland list"},
    ).json()["id"]
    tag_id = client.post("/api/v1/craves/tags", json={"name": "Noodles"}).json()["id"]

    response = client.put(
        f"/api/v1/craves/places/{place.id}",
        json={
            "status": "tried",
            "notes": "Great broth.",
            "favorite_dishes": ["Spicy miso", " spicy miso ", "Gyoza"],
            "collection_ids": [collection_id],
            "tag_ids": [tag_id],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["place_id"] == place.id
    assert body["status"] == "tried"
    assert body["notes"] == "Great broth."
    assert body["favorite_dishes"] == ["Spicy miso", "Gyoza"]
    assert body["collection_ids"] == [collection_id]
    assert body["tag_ids"] == [tag_id]

    listed = client.get("/api/v1/craves/places?status=tried").json()["items"]
    assert [row["place_id"] for row in listed] == [place.id]


def test_upsert_rejects_other_users_collection_id(db):
    owner_id = f"user-{uuid.uuid4()}"
    other_id = f"user-{uuid.uuid4()}"
    _as_user(owner_id)
    collection_id = client.post(
        "/api/v1/craves/collections",
        json={"name": "Mine only"},
    ).json()["id"]
    place = _make_place(db)

    _as_user(other_id)
    response = client.put(
        f"/api/v1/craves/places/{place.id}",
        json={"collection_ids": [collection_id]},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Unknown collection_id"


def test_upsert_rejects_invalid_status(db):
    user_id = f"user-{uuid.uuid4()}"
    _as_user(user_id)
    place = _make_place(db)

    response = client.put(
        f"/api/v1/craves/places/{place.id}",
        json={"status": "maybe_later"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Invalid Craves status"
