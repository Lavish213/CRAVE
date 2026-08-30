from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from app.db.models.city import City
from app.db.models.place import Place
from app.db.session import SessionLocal
from app.services.menu.menu_trigger import run_menu_trigger
from app.services.menu.processing.menu_orchestrator import MenuOrchestratorResult
from app.services.workers.menu_worker import MenuWorker
from scripts.populate_menus import _source_for, execution_is_authorized, main as population_main


def _city(db, label: str) -> City:
    city = City(
        id=str(uuid.uuid4()),
        name=label,
        slug=f"{label.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}",
        is_active=True,
    )
    db.add(city)
    db.commit()
    return city


def _place(db, city: City, name: str, rank_score: float) -> Place:
    place = Place(
        name=f"{name}-{uuid.uuid4().hex[:8]}",
        city_id=city.id,
        website=f"https://{uuid.uuid4().hex}.example/menu",
        is_active=True,
        rank_score=rank_score,
    )
    db.add(place)
    db.commit()
    return place


def _cleanup(*city_ids: str) -> None:
    db = SessionLocal()
    try:
        db.query(Place).filter(Place.city_id.in_(city_ids)).delete()
        db.query(City).filter(City.id.in_(city_ids)).delete()
        db.commit()
    finally:
        db.close()


def test_population_selection_is_city_scoped_and_strictly_bounded():
    db = SessionLocal()
    city_ids: list[str] = []
    try:
        target_city = _city(db, "Population Target")
        other_city = _city(db, "Population Other")
        city_ids = [target_city.id, other_city.id]
        for index in range(4):
            _place(db, target_city, "Target", 1000 - index)
        _place(db, other_city, "Other", 2000)

        selected = MenuWorker()._load_places_requiring_menu(
            db,
            city_id=target_city.id,
            limit=2,
        )

        assert len(selected) == 2
        assert {place.city_id for place in selected} == {target_city.id}
    finally:
        db.close()
        _cleanup(*city_ids)


def test_population_selection_rejects_non_http_sources():
    db = SessionLocal()
    city_id = None
    try:
        city = _city(db, "Population Source Validation")
        city_id = city.id
        invalid = _place(db, city, "Invalid", 9999)
        invalid.website = "SpritzersCafe"
        invalid_https = _place(db, city, "Invalid HTTPS", 9998)
        invalid_https.website = "https://+15106716333"
        valid = _place(db, city, "Valid", 1)
        db.commit()

        selected = MenuWorker()._load_places_requiring_menu(
            db,
            city_id=city.id,
            limit=10,
        )

        assert valid.id in {place.id for place in selected}
        assert invalid.id not in {place.id for place in selected}
        assert invalid_https.id not in {place.id for place in selected}
    finally:
        db.close()
        if city_id:
            _cleanup(city_id)


def test_population_selection_prioritizes_direct_menu_sources_over_locators():
    db = SessionLocal()
    city_id = None
    try:
        city = _city(db, "Population Source Priority")
        city_id = city.id
        locator = _place(db, city, "Locator", 9999)
        locator.website = "https://locations.example.com/ca/alameda/store-1"
        direct = _place(db, city, "Direct", 1)
        direct.website = "https://restaurant.example.com/"
        direct.menu_source_url = "https://restaurant.example.com/menu.pdf"
        db.commit()

        selected = MenuWorker()._load_places_requiring_menu(
            db,
            city_id=city.id,
            limit=1,
        )

        assert [place.id for place in selected] == [direct.id]
    finally:
        db.close()
        if city_id:
            _cleanup(city_id)


def test_population_selection_prioritizes_fresh_attempts_over_exhausted_retries():
    db = SessionLocal()
    city_id = None
    try:
        city = _city(db, "Population Retry Priority")
        city_id = city.id
        exhausted = _place(db, city, "Exhausted", 9999)
        exhausted.menu_extraction_failure_count = 4
        exhausted.menu_extraction_attempted_at = datetime.now(timezone.utc) - timedelta(days=4)
        fresh = _place(db, city, "Fresh", 1)
        db.commit()

        selected = MenuWorker()._load_places_requiring_menu(
            db,
            city_id=city.id,
            limit=1,
        )

        assert [place.id for place in selected] == [fresh.id]
    finally:
        db.close()
        if city_id:
            _cleanup(city_id)


def test_population_source_display_falls_back_past_malformed_preferred_url():
    place = type(
        "Candidate",
        (),
        {
            "menu_source_url": "https://+15106716333",
            "grubhub_url": None,
            "website": "https://restaurant.example/menu",
        },
    )()

    assert _source_for(place) == "https://restaurant.example/menu"


def test_bounded_worker_run_returns_an_auditable_summary(monkeypatch):
    db = SessionLocal()
    try:
        city = _city(db, "Population Run")
        place = _place(db, city, "Run", 5000)
    finally:
        db.close()

    worker = MenuWorker()
    monkeypatch.setattr(
        worker.orchestrator,
        "run_for_place",
        lambda *, db, place: MenuOrchestratorResult(
            place_id=place.id,
            extracted_item_count=0,
            materialized=False,
        ),
    )
    monkeypatch.setattr("app.services.workers.menu_worker.SLEEP_BETWEEN_BATCHES", 0)

    summary = worker.run(max_places=1, city_id=city.id)

    assert summary == {
        "attempted": 1,
        "errors": 0,
        "materialized": 0,
        "no_menu": 1,
    }
    _cleanup(city.id)


def test_manual_trigger_uses_the_real_orchestrator_contract(monkeypatch):
    db = SessionLocal()
    city_id = None
    try:
        city = _city(db, "Trigger Contract")
        city_id = city.id
        place = _place(db, city, "Trigger", 9000)
        calls: list[str] = []

        def run_for_place(self, *, db, place):
            calls.append(place.id)
            return MenuOrchestratorResult(place_id=place.id, materialized=False)

        monkeypatch.setattr(
            "app.services.menu.menu_trigger.MenuOrchestrator.run_for_place",
            run_for_place,
        )

        processed = run_menu_trigger(db=db, city_id=city.id, limit=1, force_refresh=True)

        assert processed == 1
        assert calls == [place.id]
    finally:
        db.close()
        if city_id:
            _cleanup(city_id)


def test_population_execution_requires_both_flags_and_exact_confirmation():
    assert execution_is_authorized(execute=False, confirmation=None) is False
    assert execution_is_authorized(execute=True, confirmation=None) is False
    assert execution_is_authorized(execute=True, confirmation="yes") is False
    assert execution_is_authorized(execute=True, confirmation="POPULATE") is True


def test_preview_and_bad_confirmation_do_not_mutate_population_state(capsys):
    db = SessionLocal()
    city_id = None
    try:
        city = _city(db, "Population Safety")
        city_id = city.id
        place = _place(db, city, "Safety", 7000)
        place_id = place.id
        city_slug = city.slug
    finally:
        db.close()

    try:
        assert population_main(["--city-slug", city_slug, "--limit", "1", "--json"]) == 0
        assert population_main(
            [
                "--city-slug",
                city_slug,
                "--limit",
                "1",
                "--execute",
                "--confirm",
                "NOT-POPULATE",
            ]
        ) == 2
        capsys.readouterr()

        db = SessionLocal()
        try:
            unchanged = db.get(Place, place_id)
            assert unchanged.menu_extraction_attempted_at is None
            assert unchanged.menu_extraction_failure_count == 0
            assert unchanged.has_menu is False
        finally:
            db.close()
    finally:
        if city_id:
            _cleanup(city_id)
