"""
Regression coverage for GET /api/v1/places/{place_id}/menu.

Found by actually running the app against seeded data: this route always
500'd for any place with real menu items. MenuItem only has a
price_cents column (canonical integer cents) — there is no `price`
attribute on the model at all — but the route did `"price": row.price`,
an AttributeError on every single row.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.menu_item import MenuItem

client = TestClient(app)


def _make_place_with_menu(*, price_cents_values):
    db = SessionLocal()
    try:
        city = City(
            id=str(uuid.uuid4()), name="Menu Route Test City",
            slug=f"menu-route-test-{uuid.uuid4().hex[:8]}",
            lat=37.8, lng=-122.27, is_active=True,
        )
        db.add(city)
        db.flush()

        place = Place(name="Menu Route Test Place", city_id=city.id, is_active=True)
        db.add(place)
        db.flush()

        for i, price_cents in enumerate(price_cents_values):
            db.add(MenuItem(
                place_id=place.id,
                name=f"Item {i}",
                price_cents=price_cents,
                category="Mains",
                fingerprint=f"{place.id}:{i}",
            ))

        db.commit()
        return place.id
    finally:
        db.close()


def test_menu_route_returns_200_with_dollar_prices_not_cents():
    place_id = _make_place_with_menu(price_cents_values=[1450, 800])

    response = client.get(f"/api/v1/places/{place_id}/menu")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 2
    prices = sorted(item["price"] for item in items)
    assert prices == [8.0, 14.5]


def test_menu_route_handles_null_price_cents():
    place_id = _make_place_with_menu(price_cents_values=[None])

    response = client.get(f"/api/v1/places/{place_id}/menu")

    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["price"] is None


def test_menu_route_returns_404_for_unknown_place():
    response = client.get(f"/api/v1/places/{uuid.uuid4()}/menu")
    assert response.status_code == 404


def test_menu_route_returns_empty_items_for_a_place_with_no_menu():
    db = SessionLocal()
    try:
        city = City(
            id=str(uuid.uuid4()), name="No Menu Test City",
            slug=f"no-menu-test-{uuid.uuid4().hex[:8]}",
            lat=37.8, lng=-122.27, is_active=True,
        )
        db.add(city)
        db.flush()
        place = Place(name="No Menu Test Place", city_id=city.id, is_active=True)
        db.add(place)
        db.commit()
        place_id = place.id
    finally:
        db.close()

    response = client.get(f"/api/v1/places/{place_id}/menu")
    assert response.status_code == 200
    assert response.json()["items"] == []
