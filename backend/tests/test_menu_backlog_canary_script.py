"""
Coverage for scripts/run_menu_backlog_canary.py -- the bounded, exact-
target menu-extraction canary. Unlike menu_worker.py's own batch run(),
this tool never selects places itself; every test here confirms it only
ever touches exactly the place_ids it was given.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.services.menu.processing.menu_orchestrator import MenuOrchestratorResult

from scripts.run_menu_backlog_canary import (
    build_preview,
    parse_place_ids,
    run_canary,
    run_is_authorized,
)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def city(db):
    c = City(
        id=str(uuid.uuid4()), name="Menu Canary Test City",
        slug=f"menu-canary-test-{uuid.uuid4().hex[:8]}", lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(c)
    db.commit()
    yield c
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_place(db, city, **overrides) -> Place:
    place = Place(
        name=overrides.pop("name", f"Test Place {uuid.uuid4().hex[:8]}"),
        city_id=city.id,
        is_active=overrides.pop("is_active", True),
        website=overrides.pop("website", "https://example.com"),
        rank_score=overrides.pop("rank_score", 0.5),
    )
    for k, v in overrides.items():
        setattr(place, k, v)
    db.add(place)
    db.commit()
    return place


def test_parse_place_ids_dedupes_while_preserving_order():
    assert parse_place_ids("a,b,a\nc") == ["a", "b", "c"]


def test_parse_place_ids_ignores_blank_lines_and_whitespace():
    assert parse_place_ids("  a  \n\n b \n") == ["a", "b"]


def test_run_is_authorized_requires_exact_match():
    assert run_is_authorized(requested_count=3, confirm_count=3)
    assert not run_is_authorized(requested_count=3, confirm_count=2)
    assert not run_is_authorized(requested_count=3, confirm_count=None)


def test_build_preview_reports_found_missing_and_inactive(db, city):
    active_place = _make_place(db, city)
    inactive_place = _make_place(db, city, is_active=False)
    missing_id = str(uuid.uuid4())

    summary, preview, places_by_id = build_preview(
        db, [active_place.id, inactive_place.id, missing_id]
    )

    assert summary["requested"] == 3
    assert summary["found"] == 2
    assert summary["missing"] == [missing_id]
    assert summary["inactive"] == [inactive_place.id]
    assert places_by_id.keys() == {active_place.id, inactive_place.id}

    found_names = {row["place_id"]: row["name"] for row in preview if row["found"]}
    assert found_names[active_place.id] == active_place.name


def test_run_canary_only_touches_the_exact_given_place_ids(db, city, monkeypatch):
    """The core guarantee this whole tool exists for: given N place IDs,
    exactly those N places are processed -- nothing selected, nothing
    skipped, nothing extra. places_by_id deliberately contains an extra
    place beyond place_ids here (simulating a stale/wider dict from an
    upstream caller) specifically so this test can tell "iterates
    place_ids" apart from the weaker "iterates places_by_id.keys()" --
    the latter would still pass a naive version of this test if
    places_by_id only ever contained exactly place_ids's rows."""
    target = _make_place(db, city, rank_score=0.1)
    untouched = _make_place(db, city, rank_score=0.99)  # would rank first in a real selection

    processed_ids = []

    def fake_run_for_place(*, db, place):
        processed_ids.append(place.id)
        return MenuOrchestratorResult(place_id=place.id, materialized=False, extracted_item_count=0)

    monkeypatch.setattr(
        "app.services.workers.menu_worker.MenuOrchestrator.run_for_place",
        lambda self, *, db, place: fake_run_for_place(db=db, place=place),
    )

    places_by_id = {target.id: target, untouched.id: untouched}
    results, run_summary = run_canary(db, place_ids=[target.id], places_by_id=places_by_id)

    assert processed_ids == [target.id]
    assert untouched.id not in processed_ids
    assert run_summary["attempted"] == 1
    assert results[0]["place_id"] == target.id


def test_load_places_requiring_menu_selection_is_never_consulted(db, city, monkeypatch):
    """run_canary must never fall back to menu_worker's own discovery
    query -- that's the exact behavior this tool exists to avoid."""
    _make_place(db, city, rank_score=0.1)

    def _fail_if_called(*args, **kwargs):
        raise AssertionError("run_canary must not call the discovery/selection query")

    monkeypatch.setattr(
        "app.services.workers.menu_worker.MenuWorker._load_places_requiring_menu",
        _fail_if_called,
    )
    monkeypatch.setattr(
        "app.services.workers.menu_worker.MenuOrchestrator.run_for_place",
        lambda self, *, db, place: MenuOrchestratorResult(
            place_id=place.id, materialized=False, extracted_item_count=0
        ),
    )

    target = _make_place(db, city)
    run_canary(db, place_ids=[target.id], places_by_id={target.id: target})


def test_run_canary_materialized_places_get_a_single_batched_recompute(db, city, monkeypatch):
    place_a = _make_place(db, city)
    place_b = _make_place(db, city)

    def fake_run_for_place(self, *, db, place):
        return MenuOrchestratorResult(place_id=place.id, materialized=True, extracted_item_count=3)

    monkeypatch.setattr(
        "app.services.workers.menu_worker.MenuOrchestrator.run_for_place",
        fake_run_for_place,
    )

    recompute_calls = []
    monkeypatch.setattr(
        "app.workers.recompute_scores_worker.recompute_places_v4",
        lambda db, places: recompute_calls.append(list(places)),
    )

    summary, preview, places_by_id = build_preview(db, [place_a.id, place_b.id])
    results, run_summary = run_canary(db, place_ids=[place_a.id, place_b.id], places_by_id=places_by_id)

    assert run_summary["materialized"] == 2
    assert len(recompute_calls) == 1
    assert {p.id for p in recompute_calls[0]} == {place_a.id, place_b.id}
