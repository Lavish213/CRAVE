from __future__ import annotations

import uuid

import pytest

from app.db.models.city import City
from app.db.models.menu_item import MenuItem
from app.db.models.place import Place
from app.db.session import SessionLocal
import scripts.deactivate_placeholder_menu_items as cleanup


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _menu_item(*, place_id: str, name: str, price_cents=None, description=None):
    return MenuItem(
        place_id=place_id,
        name=name,
        fingerprint=str(uuid.uuid4()),
        price_cents=price_cents,
        description=description,
    )


def test_confirmation_is_exact():
    assert cleanup.execution_is_authorized(
        apply=True, confirmation=cleanup.APPLY_CONFIRMATION
    )
    assert not cleanup.execution_is_authorized(apply=True, confirmation="apply")
    assert cleanup.simulation_is_authorized(
        simulate=True, confirmation=cleanup.SIMULATE_CONFIRMATION
    )
    assert not cleanup.simulation_is_authorized(simulate=True, confirmation="simulate")


def test_only_unmistakable_placeholders_are_deactivated(db):
    city_id = str(uuid.uuid4())
    place_id = str(uuid.uuid4())
    db.add(City(id=city_id, slug=f"cleanup-{city_id}", name="Cleanup City"))
    db.add(Place(id=place_id, name="Test Kitchen", city_id=city_id, lat=1, lng=1))
    rows = [
        _menu_item(place_id=place_id, name="Test"),
        _menu_item(place_id=place_id, name="Dummy item 2", price_cents=0),
        _menu_item(place_id=place_id, name="Test Kitchen Burger", price_cents=1200),
        _menu_item(place_id=place_id, name="Test", description="A real tasting plate"),
        _menu_item(place_id=place_id, name="Test", price_cents=500),
    ]
    db.add_all(rows)
    db.commit()

    findings = cleanup.deactivate(db)

    assert {finding.item_name for finding in findings} == {"Test", "Dummy item 2"}
    assert rows[0].is_active is False
    assert rows[1].is_active is False
    assert all(row.is_active for row in rows[2:])

    db.query(MenuItem).filter(MenuItem.place_id == place_id).delete(
        synchronize_session=False
    )
    db.query(Place).filter(Place.id == place_id).delete()
    db.query(City).filter(City.id == city_id).delete()
    db.commit()
