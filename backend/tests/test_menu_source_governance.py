from __future__ import annotations

import uuid

import pytest

from app.db.models.city import City
from app.db.models.menu_source import MenuSource
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.services.menu.discovery.menu_source_manager import menu_source_manager
from app.services.menu.fetch.fetch_strategy_router import (
    STRATEGY_DIRECT,
    STRATEGY_FAIL_FAST,
    classify_fetch_strategy,
)
from app.services.menu import menu_extraction_router
from app.services.menu.menu_extraction_router import extract_menu
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


def test_menu_source_records_latest_failure_reason_immediately(db, city):
    place = Place(
        name="Failure Reason Test",
        city_id=city.id,
        is_active=True,
        website="https://example.test",
    )
    db.add(place)
    db.commit()

    source_url = "https://order.toasttab.com/online/failure-reason-test"
    try:
        menu_source_manager.record_discovery(
            db=db,
            place_id=place.id,
            source_url=source_url,
            provider="toast",
            source_type="provider",
            confidence=0.97,
        )
        db.commit()

        menu_source_manager.record_failure(
            db=db,
            place_id=place.id,
            source_url=source_url,
            reason="access_blocked:provider_api_required",
        )
        db.commit()

        row = db.query(MenuSource).filter(MenuSource.place_id == place.id).one()
        assert row.failure_count == 1
        assert row.last_failure_at is not None
        assert row.last_failure_reason == "access_blocked:provider_api_required"
        assert row.invalidation_reason is None
    finally:
        db.query(MenuSource).filter(MenuSource.place_id == place.id).delete()
        db.query(Place).filter(Place.id == place.id).delete()
        db.commit()


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


def test_advanced_extraction_blocks_provider_api_required_direct_urls(monkeypatch):
    def _browser_should_not_run(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("browser escalation should not run for Toast")

    monkeypatch.setattr(
        "app.services.menu.menu_extraction_router.fetch_with_browser",
        _browser_should_not_run,
    )

    assert extract_menu(
        html="",
        url="https://order.toasttab.com/online/provider-wall-test",
        place_id="place-1",
    ) == []


def test_advanced_api_discovery_skips_provider_api_required_endpoints(monkeypatch):
    monkeypatch.setattr(
        menu_extraction_router,
        "discover_api_endpoints",
        lambda html, url: ["https://order.toasttab.com/api/menus/v3/restaurant/demo"],
    )

    def _api_should_not_run(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("Toast API endpoint should not be probed")

    monkeypatch.setattr(menu_extraction_router, "extract_api_menu", _api_should_not_run)
    monkeypatch.setattr(menu_extraction_router, "extract_graphql_menu", _api_should_not_run)

    assert menu_extraction_router._safe_api_extract(
        "<html><script src='/menu.js'></script></html>",
        "https://example-restaurant.test/menu",
    ) == []


def test_advanced_iframe_discovery_skips_provider_api_required_iframes(monkeypatch):
    monkeypatch.setattr(
        menu_extraction_router,
        "detect_menu_iframes",
        lambda html, url: ["https://ordering.chownow.com/order/123"],
    )

    def _fetch_should_not_run(*args, **kwargs):  # pragma: no cover - failure path
        raise AssertionError("ChowNow iframe should not be fetched")

    monkeypatch.setattr(menu_extraction_router, "fetch", _fetch_should_not_run)

    assert menu_extraction_router._safe_iframe_extract(
        "<html><iframe src='https://ordering.chownow.com/order/123'></iframe></html>",
        "https://example-restaurant.test/menu",
        "Example Restaurant",
    ) == []
