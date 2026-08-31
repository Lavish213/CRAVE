"""
Coverage for app.services.workers.menu_worker — specifically the
menu-extraction backoff that never actually existed despite
Place.menu_extraction_failure_count / menu_extraction_attempted_at having
existed since the truth-stabilization migration with a documented
schedule in their column comments ("1=1h, 2=4h, 3=24h, 4+=72h").

Before this fix: _load_places_requiring_menu only excluded places that
already had a menu PlaceTruth row, and materialize_menu_truth only ever
writes one on SUCCESS — a place that came up empty (bad site, unparsable
PDF, JS wall) never got excluded, so the same top-rank_score places
occupied every single batch, every run, forever, starving the rest of
the catalog. This is the single largest lever on menu coverage: most of
the catalog was never even attempted, not an extractor-quality problem.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.services.workers.menu_worker import MenuWorker
from app.services.menu.processing.menu_orchestrator import MenuOrchestratorResult


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_city(db) -> City:
    city = City(
        id=str(uuid.uuid4()),
        name="Menu Worker Test City",
        slug=f"menu-worker-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    return city


def _make_place(db, city, **overrides) -> Place:
    place = Place(
        name=overrides.pop("name", f"Test Place {uuid.uuid4().hex[:8]}"),
        city_id=city.id,
        is_active=True,
        website=overrides.pop("website", "https://example.com"),
        rank_score=overrides.pop("rank_score", 0.5),
    )
    for k, v in overrides.items():
        setattr(place, k, v)
    db.add(place)
    db.commit()
    return place


class TestBackoffQuery:
    def test_never_attempted_place_is_eligible(self, db):
        city = _make_city(db)
        place = _make_place(db, city)

        worker = MenuWorker()
        results = worker._load_places_requiring_menu(db)

        assert place.id in {p.id for p in results}

    def test_recently_failed_once_is_excluded(self, db):
        city = _make_city(db)
        place = _make_place(
            db, city,
            menu_extraction_failure_count=1,
            menu_extraction_attempted_at=datetime.now(timezone.utc) - timedelta(minutes=30),
        )

        worker = MenuWorker()
        results = worker._load_places_requiring_menu(db)

        assert place.id not in {p.id for p in results}

    def test_failed_once_past_the_1h_window_is_eligible_again(self, db):
        city = _make_city(db)
        place = _make_place(
            db, city,
            menu_extraction_failure_count=1,
            menu_extraction_attempted_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )

        worker = MenuWorker()
        results = worker._load_places_requiring_menu(db)

        assert place.id in {p.id for p in results}

    def test_failed_three_times_needs_the_24h_window_not_the_1h_one(self, db):
        city = _make_city(db)
        place = _make_place(
            db, city,
            menu_extraction_failure_count=3,
            menu_extraction_attempted_at=datetime.now(timezone.utc) - timedelta(hours=2),
        )

        worker = MenuWorker()
        results = worker._load_places_requiring_menu(db)

        # Only 2h since the 3rd failure — the schedule requires 24h at
        # that failure count, so this must NOT be eligible yet.
        assert place.id not in {p.id for p in results}

    def test_failed_four_or_more_times_uses_the_72h_ceiling(self, db):
        city = _make_city(db)
        still_backing_off = _make_place(
            db, city,
            menu_extraction_failure_count=9,
            menu_extraction_attempted_at=datetime.now(timezone.utc) - timedelta(hours=48),
        )
        past_ceiling = _make_place(
            db, city,
            menu_extraction_failure_count=9,
            menu_extraction_attempted_at=datetime.now(timezone.utc) - timedelta(hours=73),
        )

        worker = MenuWorker()
        result_ids = {p.id for p in worker._load_places_requiring_menu(db)}

        assert still_backing_off.id not in result_ids
        assert past_ceiling.id in result_ids

    def test_a_place_with_a_recently_checked_menu_is_excluded(self, db):
        # A place checked within MENU_STALENESS_DAYS must stay excluded —
        # failure_count reset to 0 by a recent success (eligible by backoff
        # in isolation) must not override the "checked recently" exclusion.
        from app.db.models.place_truth import PlaceTruth
        from app.services.workers import menu_worker as menu_worker_module

        city = _make_city(db)
        place = _make_place(
            db, city,
            menu_extraction_failure_count=0,
            menu_extraction_attempted_at=datetime.now(timezone.utc),
        )
        db.add(PlaceTruth(
            place_id=place.id, truth_type="menu", truth_value="menu", confidence=0.9,
        ))
        db.commit()

        worker = MenuWorker()
        results = worker._load_places_requiring_menu(db)

        assert place.id not in {p.id for p in results}

    def test_a_place_with_a_stale_menu_becomes_eligible_again(self, db):
        # The actual staleness re-verification feature: an existing menu
        # older than MENU_STALENESS_DAYS since its last real check must
        # become eligible again — menus go stale (price changes, a
        # redesign that breaks the extractor, a closed restaurant), and
        # nothing before this ever re-checked a place once it had one.
        from app.db.models.place_truth import PlaceTruth
        from app.services.workers.menu_worker import MENU_STALENESS_DAYS

        city = _make_city(db)
        stale_at = datetime.now(timezone.utc) - timedelta(days=MENU_STALENESS_DAYS + 1)
        place = _make_place(
            db, city, menu_extraction_failure_count=0, menu_extraction_attempted_at=stale_at,
        )
        db.add(PlaceTruth(
            place_id=place.id, truth_type="menu", truth_value="menu", confidence=0.9,
        ))
        db.commit()

        worker = MenuWorker()
        results = worker._load_places_requiring_menu(db)

        assert place.id in {p.id for p in results}

    def test_a_place_with_a_menu_never_stamped_is_eligible(self, db):
        # Places that got a menu before this staleness mechanism existed
        # have menu_extraction_attempted_at = NULL (success never stamped
        # it before this change) — treated as eligible for one catch-up
        # check rather than needing a data migration to backfill the column.
        from app.db.models.place_truth import PlaceTruth

        city = _make_city(db)
        place = _make_place(db, city, menu_extraction_failure_count=0)
        db.add(PlaceTruth(
            place_id=place.id, truth_type="menu", truth_value="menu", confidence=0.9,
        ))
        db.commit()

        worker = MenuWorker()
        results = worker._load_places_requiring_menu(db)

        assert place.id in {p.id for p in results}


class TestRunRecordsFailures:
    # MAX_PLACES_PER_RUN=1 in every test below means run() processes only
    # the single first row _load_places_requiring_menu returns (ordered by
    # rank_score DESC). tests/conftest.py's DATABASE_URL points at one
    # on-disk SQLite file shared by the whole test run, and TestBackoffQuery
    # above leaves several of its own eligible (website set, no menu truth)
    # places behind — a realistic rank_score here isn't enough to guarantee
    # this test's place sorts first among them. A distinctly out-of-range
    # score sidesteps that instead of depending on collection order.
    _FIRST_IN_BATCH_RANK_SCORE = 999.0

    def test_an_empty_result_records_a_failure_and_backs_off_next_load(self, db, monkeypatch):
        city = _make_city(db)
        place = _make_place(db, city, rank_score=self._FIRST_IN_BATCH_RANK_SCORE)

        worker = MenuWorker()
        monkeypatch.setattr(
            worker.orchestrator, "run_for_place",
            lambda *, db, place: MenuOrchestratorResult(place_id=place.id, materialized=False),
        )
        # Force exactly one batch/place so run() terminates promptly.
        monkeypatch.setattr("app.services.workers.menu_worker.MAX_PLACES_PER_RUN", 1)
        monkeypatch.setattr("app.services.workers.menu_worker.SLEEP_BETWEEN_BATCHES", 0)

        worker.run()

        db.refresh(place)
        assert place.menu_extraction_failure_count == 1
        assert place.menu_extraction_attempted_at is not None
        assert place.has_menu is False

        # And it must not be immediately eligible again.
        results = worker._load_places_requiring_menu(db)
        assert place.id not in {p.id for p in results}

    def test_an_exception_during_extraction_also_records_a_failure(self, db, monkeypatch):
        city = _make_city(db)
        place = _make_place(db, city, rank_score=self._FIRST_IN_BATCH_RANK_SCORE)

        worker = MenuWorker()

        def _boom(*, db, place):
            raise RuntimeError("extractor blew up")

        monkeypatch.setattr(worker.orchestrator, "run_for_place", _boom)
        monkeypatch.setattr("app.services.workers.menu_worker.MAX_PLACES_PER_RUN", 1)
        monkeypatch.setattr("app.services.workers.menu_worker.SLEEP_BETWEEN_BATCHES", 0)

        worker.run()

        db.refresh(place)
        assert place.menu_extraction_failure_count == 1
        assert place.menu_extraction_attempted_at is not None

    def test_a_materialized_result_resets_failure_count_and_sets_has_menu(self, db, monkeypatch):
        city = _make_city(db)
        place = _make_place(
            db, city,
            rank_score=self._FIRST_IN_BATCH_RANK_SCORE,
            menu_extraction_failure_count=2,
            menu_extraction_attempted_at=datetime.now(timezone.utc) - timedelta(hours=10),
        )

        worker = MenuWorker()
        monkeypatch.setattr(
            worker.orchestrator, "run_for_place",
            lambda *, db, place: MenuOrchestratorResult(
                place_id=place.id, materialized=True, extracted_item_count=5,
            ),
        )
        monkeypatch.setattr("app.services.workers.menu_worker.MAX_PLACES_PER_RUN", 1)
        monkeypatch.setattr("app.services.workers.menu_worker.SLEEP_BETWEEN_BATCHES", 0)
        # recompute_places_v4 touches scoring machinery unrelated to this
        # test; stub it so a materialized result doesn't need a full
        # scoring fixture.
        monkeypatch.setattr(
            "app.services.workers.menu_worker.recompute_places_v4",
            lambda db, places: None,
        )

        # Naive comparison below — SQLite round-trips DateTime columns as
        # naive even though the value was written tz-aware; not a
        # production concern (Postgres preserves tz-awareness), just a
        # test-storage quirk.
        before = datetime.now(timezone.utc).replace(tzinfo=None)
        worker.run()

        db.refresh(place)
        assert place.has_menu is True
        assert place.menu_extraction_failure_count == 0
        # Stamped on success too (not just failure) — this is the staleness
        # clock that eventually makes an already-menu'd place eligible for
        # re-checking again (see TestBackoffQuery's staleness tests).
        assert place.menu_extraction_attempted_at is not None
        assert place.menu_extraction_attempted_at.replace(tzinfo=None) >= before

    def test_recompute_is_called_once_per_batch_not_once_per_materialized_place(self, db, monkeypatch):
        """recompute_places_v4's own _fetch_signal_context is explicitly
        batch-fetch, "never per-place" -- calling recompute once per
        materialized place instead of once for the whole batch defeats that
        design (N places -> N x as many signal queries). This locks in that
        a batch with multiple materialized places makes exactly one
        recompute_places_v4 call, covering all of them together."""
        city = _make_city(db)
        place_a = _make_place(db, city, rank_score=0.9)
        place_b = _make_place(db, city, rank_score=0.8)

        worker = MenuWorker()
        monkeypatch.setattr(
            worker.orchestrator, "run_for_place",
            lambda *, db, place: MenuOrchestratorResult(
                place_id=place.id, materialized=True, extracted_item_count=3,
            ),
        )
        monkeypatch.setattr("app.services.workers.menu_worker.MAX_PLACES_PER_RUN", 2)
        monkeypatch.setattr("app.services.workers.menu_worker.BATCH_SIZE", 2)
        monkeypatch.setattr("app.services.workers.menu_worker.SLEEP_BETWEEN_BATCHES", 0)

        recompute_calls = []
        monkeypatch.setattr(
            "app.services.workers.menu_worker.recompute_places_v4",
            lambda db, places: recompute_calls.append(list(places)),
        )

        # Scoped to this test's own city -- this file's `db` fixture has no
        # teardown between tests, so without this the batch could pick up
        # places left over from other tests instead of place_a/place_b.
        worker.run(city_id=city.id)

        assert len(recompute_calls) == 1
        assert {p.id for p in recompute_calls[0]} == {place_a.id, place_b.id}
