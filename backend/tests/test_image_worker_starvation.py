"""
Coverage for ImageWorker._select_places' starvation-reserve split, and its
separate stale-primary-image refresh reserve.

Starvation reserve: confirmed happening in production, a small-town city
(Lodi) had 48 active places, all needing image work (zero images each), but
zero of them were ever picked up across 622 consecutive successful
image_ingestion runs. _select_places ordered strictly by rank_score DESC
with a plain LIMIT and no rotation — a place with a naturally low
rank_score can be permanently outranked by every other place still needing
image work, since discovery keeps adding new candidates that refill the
top of that ordering forever.

Stale-refresh reserve: confirmed live in production via a direct API call —
a currently-listed, currently-active place's stored primary_image_url
404'd from Google's own Places API (New) media endpoint. Google's photo
resource names aren't permanent, but _needs_image_work_clause only selects
places with too few images or no primary at all, so once a place clears
that bar even once it was never revisited again — STALE_IMAGE_DAYS existed
as a constant but nothing ever used it until this reserve.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.workers.image_worker import ImageWorker, MIN_IMAGE_COUNT, STALE_IMAGE_DAYS


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


def _make_place_with_primary_image(db, city, *, rank_score: float, image_age_days: int) -> Place:
    # MIN_IMAGE_COUNT total images (not just 1) — a place with fewer than
    # that already matches _needs_image_work_clause on its own (regardless
    # of how old its primary is), which would let the ordinary priority
    # query claim it first and starve the stale-refresh reserve of
    # anything to select. Giving it a full gallery isolates "primary image
    # is stale" as the only reason this place should need work.
    p = _make_place(db, city, rank_score=rank_score)
    db.flush()
    primary = PlaceImage(
        place_id=p.id,
        url=f"https://example.test/{uuid.uuid4().hex}.jpg",
        is_primary=True,
    )
    db.add(primary)
    for _ in range(MIN_IMAGE_COUNT - 1):
        db.add(
            PlaceImage(
                place_id=p.id,
                url=f"https://example.test/{uuid.uuid4().hex}.jpg",
                is_primary=False,
            )
        )
    db.flush()
    primary.created_at = datetime.now(timezone.utc) - timedelta(days=image_age_days)
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
        selected, _stale_ids = worker._select_places(
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
        selected, stale_ids = worker._select_places(
            db=db, limit=50, force_refresh=False, place_ids=target_ids,
        )
        assert {p.id for p in selected} == set(target_ids)
        assert stale_ids == set()
    finally:
        all_ids = [p.id for p in places]
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()


def test_select_places_small_limit_skips_fairness_split(db, city):
    places = [_make_place(db, city, rank_score=float(i)) for i in range(3)]
    db.commit()

    try:
        worker = ImageWorker()
        selected, stale_ids = worker._select_places(
            db=db, limit=1, force_refresh=False, place_ids=None,
        )
        assert len(selected) == 1
        assert stale_ids == set()
        # Highest rank_score should win when there's no room for a fairness
        # slot at all.
        assert selected[0].id == places[-1].id
    finally:
        all_ids = [p.id for p in places]
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()


def test_select_places_reserves_slots_for_stale_primary_images(db, city):
    # These places already have a primary image (they'd never match
    # _needs_image_work_clause), but it's well past STALE_IMAGE_DAYS — the
    # exact Lodi-shaped tail for the photo-expiry bug: real, currently-
    # active places whose stored Google photo reference has likely gone
    # invalid, but nothing would ever revisit them without this reserve.
    stale_places = [
        _make_place_with_primary_image(
            db, city, rank_score=90.0 - i, image_age_days=STALE_IMAGE_DAYS + 10 + i,
        )
        for i in range(3)
    ]
    # Plenty of places that plainly need image work too, so the stale
    # reserve has to compete for batch space instead of being the only
    # thing selected.
    needs_work_places = [
        _make_place(db, city, rank_score=100.0 - i) for i in range(40)
    ]
    db.commit()

    all_ids = [p.id for p in stale_places + needs_work_places]
    try:
        worker = ImageWorker()
        selected, stale_ids = worker._select_places(
            db=db, limit=20, force_refresh=False, place_ids=None,
        )
        selected_ids = {p.id for p in selected}

        assert len(selected) == 20
        stale_place_ids = {p.id for p in stale_places}
        assert stale_ids, "stale-refresh reserve should surface at least one candidate"
        assert stale_ids <= stale_place_ids
        assert stale_ids <= selected_ids
    finally:
        db.query(PlaceImage).filter(PlaceImage.place_id.in_(all_ids)).delete(synchronize_session=False)
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()


def test_select_places_does_not_treat_a_fresh_primary_image_as_stale(db, city):
    # Regression guard: a place with a normal, recently-set primary image
    # must not get swept into the stale-refresh reserve (and therefore
    # force_refresh=True in run()) just because it happens to also need
    # more images elsewhere in the batch.
    fresh_place = _make_place_with_primary_image(
        db, city, rank_score=95.0, image_age_days=1,
    )
    db.commit()

    all_ids = [fresh_place.id]
    try:
        worker = ImageWorker()
        _selected, stale_ids = worker._select_places(
            db=db, limit=10, force_refresh=False, place_ids=None,
        )
        assert fresh_place.id not in stale_ids
    finally:
        db.query(PlaceImage).filter(PlaceImage.place_id.in_(all_ids)).delete(synchronize_session=False)
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()
