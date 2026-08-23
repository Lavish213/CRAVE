"""
Regression test for a real bug introduced (and caught) in this same
session's own eager-loading cleanup: Place.city was changed from
lazy="selectin" to lazy="select" after a whole-app grep found "zero real
usages" -- but that grep, based on literal `.city` dot-access, missed
`getattr(place, "city", None)` in
app/workers/recompute_scores_worker.py::_score_batch(), which resolves
city-aware scoring weights for every place in a batch of up to 500,
every 15 minutes (app/scheduler.py::_job_score_recompute).

Fixed by adding an explicit `.options(selectinload(Place.city))` to that
scheduler query (the same pattern app/services/scoring/recompute_scores.py
already uses for Place.categories) -- not by reverting the model-level
default, which was correctly removed everywhere it was genuinely unused.

This test proves the fix with real statement counts, not just a
functional assertion (which wouldn't distinguish "batched" from "one
query per place" -- both return correct data, only one is efficient):
with 5 places each in a DIFFERENT city (so SQLAlchemy's per-session
identity map can't accidentally dedupe repeated lookups of the *same*
city), the eager-loaded query must stay flat regardless of how many
distinct cities are represented, while the lazy default would add one
query per distinct city.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import selectinload

from app.db.session import SessionLocal, engine
from app.db.models.city import City
from app.db.models.place import Place
from app.workers.recompute_scores_worker import _score_batch


@pytest.fixture
def db():
    created = {"place_ids": [], "city_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
        if created["place_ids"]:
            session.query(Place).filter(
                Place.id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
        if created["city_ids"]:
            session.query(City).filter(
                City.id.in_(created["city_ids"])
            ).delete(synchronize_session=False)
        session.commit()
        session.close()


def _seed_places_across_distinct_cities(session, created, *, count: int) -> list[str]:
    suffix = uuid.uuid4().hex[:8]
    place_ids = []
    for i in range(count):
        city = City(
            id=str(uuid.uuid4()), name=f"Score Batch Test City {i} {suffix}",
            slug=f"score-batch-test-{i}-{suffix}", lat=37.8, lng=-122.27, is_active=True,
        )
        session.add(city)
        session.flush()
        created["city_ids"].append(city.id)

        place = Place(name=f"Score Batch Test Place {i}", city_id=city.id, is_active=True)
        session.add(place)
        session.flush()
        created["place_ids"].append(place.id)
        place_ids.append(place.id)

    session.commit()
    return place_ids


def _count_statements_for_score_batch(place_ids: list[str], *, with_eager_load: bool) -> int:
    # Fresh session (empty identity map) -- app/scheduler.py's
    # _job_score_recompute always starts from a brand-new SessionLocal(),
    # so reusing the seeding session here would hide the real behavior
    # (a city already in the identity map is never re-queried regardless
    # of loading strategy).
    fresh_db = SessionLocal()
    try:
        stmt = select(Place).where(Place.id.in_(place_ids))
        if with_eager_load:
            stmt = stmt.options(selectinload(Place.city))
        places = fresh_db.execute(stmt).scalars().all()

        count = {"n": 0}

        def _before_cursor_execute(*args, **kwargs):
            count["n"] += 1

        event.listen(engine, "before_cursor_execute", _before_cursor_execute)
        try:
            _score_batch(fresh_db, places)
        finally:
            event.remove(engine, "before_cursor_execute", _before_cursor_execute)

        return count["n"]
    finally:
        fresh_db.close()


def test_score_batch_city_lookup_does_not_scale_with_distinct_city_count(db):
    session, created = db
    place_ids = _seed_places_across_distinct_cities(session, created, count=5)

    with_eager = _count_statements_for_score_batch(place_ids, with_eager_load=True)
    without_eager = _count_statements_for_score_batch(place_ids, with_eager_load=False)

    # Without the eager-load option, 5 distinct cities means 5 extra
    # queries -- one lazy load per place, since the identity map can only
    # dedupe repeated lookups of the *same* city.
    assert without_eager - with_eager >= 4, (
        f"expected the lazy-default path to cost several more statements "
        f"than the eager-loaded path (5 distinct cities): "
        f"with_eager={with_eager}, without_eager={without_eager}"
    )
