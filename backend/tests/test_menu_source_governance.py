from __future__ import annotations

import uuid

import pytest

from app.db.models.city import City
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.services.menu.fetch.fetch_strategy_router import (
    STRATEGY_DIRECT,
    STRATEGY_FAIL_FAST,
    classify_fetch_strategy,
)
from app.services.menu.processing.menu_orchestrator import MenuOrchestrator


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def city(db):
    suffix = uuid.uuid4().hex[:8]
    row = City(
        id=str(uuid.uuid4()),
        slug=f"menu-source-gov-{suffix}",
        name=f"Menu Source Governance {suffix}",
        is_active=True,
    )
    db.add(row)
    db.commit()
    yield row
    db.query(City).filter(City.id == row.id).delete()
    db.commit()


def test_toast_and_chownow_are_provider_access_blocks():
    toast = classify_fetch_strategy("https://order.toasttab.com/online/example")
    assert toast.strategy == STRATEGY_FAIL_FAST
    assert toast.provider == "toast"
    assert toast.blocked_reason == "provider_api_required"
    assert toast.needs_auth is True

    chownow = classify_fetch_strategy("https://ordering.chownow.com/order/123")
    assert chownow.strategy == STRATEGY_FAIL_FAST
    assert chownow.provider == "chownow"
    assert chownow.blocked_reason == "provider_api_required"
    assert chownow.needs_auth is True


def test_square_site_remains_direct_public_source():
    result = classify_fetch_strategy("https://house-coffee-co.square.site")
    assert result.strategy == STRATEGY_DIRECT
    assert result.blocked_reason is None


def test_menu_orchestrator_does_not_fetch_provider_api_required_urls(
    db, city, monkeypatch
):
    place = Place(
        name="Provider Wall Test",
        city_id=city.id,
        is_active=True,
        website="https://order.toasttab.com/online/provider-wall-test",
    )
    db.add(place)
    db.commit()

    def _fetch_should_not_run(url: str):  # pragma: no cover - failure path
        raise AssertionError(f"fetch_html should not run for {url}")

    monkeypatch.setattr(
        "app.services.menu.processing.menu_orchestrator.fetch_html",
        _fetch_should_not_run,
    )

    try:
        result = MenuOrchestrator().run_for_place(db=db, place=place)

        assert result.extracted_item_count == 0
        assert result.materialized is False
    finally:
        db.query(Place).filter(Place.id == place.id).delete()
        db.commit()
