"""
Coverage for ImageWorker._select_places' starvation-reserve split.

Confirmed happening in production: a small-town city (Lodi) had 48 active
places, all needing image work (zero images each), but zero of them were
ever picked up across 622 consecutive successful image_ingestion runs.
_select_places ordered strictly by rank_score DESC with a plain LIMIT and
no rotation — a place with a naturally low rank_score can be permanently
outranked by every other place still needing image work, since discovery
keeps adding new candidates that refill the top of that ordering forever.
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
from app.workers.image_worker import ImageWorker


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
    c = City(slug=f"starve-test-{suffix}", name=f"Starve Test City {suffix}")
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
    )
    db.add(p)
    return p


def test_select_places_reserves_slots_for_low_rank_places_needing_work(db, city):
    # The Lodi-shaped tail: a handful of long-established, low-rank places
    # that need image work. Created first, so they're also the oldest by
    # created_at — same as production, where Lodi's places already existed
    # before the newer high-rank discoveries below piled up behind them.
    low_rank_places = [
        _make_place(db, city, rank_score=0.0) for _ in range(5)
    ]
    # Far more high-rank places need work than fit in one batch, and keep
    # arriving after the low-rank ones — the exact production shape (a
    # constant backlog of higher-signal places at the top of the
    # rank_score ordering, continuously refilled by discovery).
    high_rank_places = [
        _make_place(db, city, rank_score=100.0 - i) for i in range(80)
    ]
    db.commit()

    try:
        worker = ImageWorker()
        selected = worker._select_places(
            db=db, limit=50, force_refresh=False, place_ids=None,
        )
        selected_ids = {p.id for p in selected}

        assert len(selected) == 50
        low_rank_ids = {p.id for p in low_rank_places}
        assert selected_ids & low_rank_ids, (
            "starvation reserve should surface at least one low-rank place "
            "even though 80 higher-rank places also need work"
        )
    finally:
        all_ids = [p.id for p in high_rank_places + low_rank_places]
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()


def test_select_places_with_place_ids_bypasses_fairness_split(db, city):
    places = [_make_place(db, city, rank_score=float(i)) for i in range(3)]
    db.commit()

    try:
        worker = ImageWorker()
        target_ids = [places[0].id, places[1].id]
        selected = worker._select_places(
            db=db, limit=50, force_refresh=False, place_ids=target_ids,
        )
        assert {p.id for p in selected} == set(target_ids)
    finally:
        all_ids = [p.id for p in places]
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()


def test_select_places_small_limit_skips_fairness_split(db, city):
    places = [_make_place(db, city, rank_score=float(i)) for i in range(3)]
    db.commit()

    try:
        worker = ImageWorker()
        selected = worker._select_places(
            db=db, limit=1, force_refresh=False, place_ids=None,
        )
        assert len(selected) == 1
        # Highest rank_score should win when there's no room for a fairness
        # slot at all.
        assert selected[0].id == places[-1].id
    finally:
        all_ids = [p.id for p in places]
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()
