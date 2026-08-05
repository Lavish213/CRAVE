"""
Coverage for MenuWorker._load_places_requiring_menu's starvation-reserve
split — same bug class as ImageWorker._select_places (see
test_image_worker_starvation.py), independently confirmed here: the query
ordered strictly by rank_score DESC with a plain LIMIT and no rotation, so a
place with a naturally low rank_score and a valid menu source (website/
grubhub_url/menu_source_url) that has never been attempted could be
permanently outranked by every other place still needing menu work, since
discovery keeps adding new candidates that refill the top of that ordering
forever. The existing backoff mechanism only protects against a
repeat-failing place hogging every run — it does nothing for a place that's
simply never been tried.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.services.workers.menu_worker import MenuWorker, BATCH_SIZE


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def city(db):
    suffix = uuid.uuid4().hex[:8]
    c = City(slug=f"menu-starve-test-{suffix}", name=f"Menu Starve Test City {suffix}")
    db.add(c)
    db.commit()
    yield c
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_place(db, city, *, rank_score: float) -> Place:
    p = Place(
        name=f"Place {uuid.uuid4().hex[:8]}",
        city_id=city.id,
        is_active=True,
        rank_score=rank_score,
        website=f"https://example-{uuid.uuid4().hex[:8]}.test",
    )
    db.add(p)
    return p


def test_load_places_requiring_menu_reserves_slots_for_low_rank_places(db, city):
    # The Lodi-shaped tail: a handful of long-established, low-rank places
    # that need menu work and have never been attempted.
    low_rank_places = [
        _make_place(db, city, rank_score=0.0) for _ in range(5)
    ]
    # Far more high-rank places need work than fit in one batch, and keep
    # arriving after the low-rank ones — the exact production shape.
    high_rank_places = [
        _make_place(db, city, rank_score=100.0 - i) for i in range(80)
    ]
    db.commit()

    try:
        worker = MenuWorker()
        selected = worker._load_places_requiring_menu(db)
        selected_ids = {p.id for p in selected}

        assert len(selected) == BATCH_SIZE
        low_rank_ids = {p.id for p in low_rank_places}
        assert selected_ids & low_rank_ids, (
            "starvation reserve should surface at least one low-rank place "
            "even though 80 higher-rank places also need menu work"
        )
    finally:
        all_ids = [p.id for p in high_rank_places + low_rank_places]
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()
