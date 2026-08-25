"""
Coverage for ImageWorker.run()'s stale-refresh branching: a place selected
via the stale-primary-image reserve (see test_image_worker_starvation.py)
must go through StaleImageRefresher.refresh_primary, never through
ImageIngestService.ingest_place_images — running the normal gallery-
rebuild pipeline on a stale-refresh cycle would accumulate a fresh,
never-pruned set of gallery rows for the same place every ~30 days,
since Google's photo references aren't stable across separate fetches
(see StaleImageRefresher's own docstring). This is the regression guard
for that specific wiring, at the level a scheduler-triggered run() call
actually exercises it.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.workers.image_worker import ImageWorker, MIN_IMAGE_COUNT


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
    c = City(slug=f"run-stale-test-{suffix}", name=f"Run Stale Test City {suffix}")
    db.add(c)
    db.commit()
    yield c
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


# _select_places has no city filter — it selects eligible places across
# the whole table, and _stale_primary_clause's oldest-primary-first
# ordering means a stray older stale row left by another test (or a
# different run order) could out-rank ours for the reserve's single slot.
# An extreme age keeps our test place deterministically the oldest
# regardless of what else exists in the shared dev/test DB.
_VERY_STALE_DAYS = 100_000


def _make_stale_place(db, city, *, image_age_days: int = _VERY_STALE_DAYS) -> Place:
    p = Place(name=f"Stale {uuid.uuid4().hex[:8]}", city_id=city.id, is_active=True, rank_score=0.5)
    db.add(p)
    db.flush()
    primary = PlaceImage(place_id=p.id, url="places/OLD_REF/photos/abc", is_primary=True)
    db.add(primary)
    for _ in range(MIN_IMAGE_COUNT - 1):
        db.add(PlaceImage(place_id=p.id, url=f"https://example.test/{uuid.uuid4().hex}.jpg", is_primary=False))
    db.flush()
    primary.created_at = datetime.now(timezone.utc) - timedelta(days=image_age_days)
    db.commit()
    return p


def _make_needs_work_place(db, city, *, rank_score: float) -> Place:
    p = Place(name=f"NeedsWork {uuid.uuid4().hex[:8]}", city_id=city.id, is_active=True, rank_score=rank_score)
    db.add(p)
    return p


def test_run_routes_stale_places_through_refresher_not_ingest_service(db, city):
    stale_place = _make_stale_place(db, city)
    # Enough plain "needs work" places that the stale place has to compete
    # for reserve space rather than being the only candidate at all.
    needs_work_places = [_make_needs_work_place(db, city, rank_score=100.0 - i) for i in range(20)]
    db.commit()

    all_ids = [p.id for p in [stale_place] + needs_work_places]
    try:
        mock_ingest_service = MagicMock()
        mock_ingest_service.ingest_place_images.return_value = [MagicMock()]
        mock_refresher = MagicMock()
        mock_refresher.refresh_primary.return_value = True

        worker = ImageWorker(ingest_service=mock_ingest_service, stale_refresher=mock_refresher)
        worker.run(db=db, limit=10, force_refresh=False)

        refreshed_place_ids = {
            call.kwargs["place"].id for call in mock_refresher.refresh_primary.call_args_list
        }
        ingested_place_ids = {
            call.kwargs["place"].id for call in mock_ingest_service.ingest_place_images.call_args_list
        }

        assert stale_place.id in refreshed_place_ids
        assert stale_place.id not in ingested_place_ids
    finally:
        db.query(PlaceImage).filter(PlaceImage.place_id.in_(all_ids)).delete(synchronize_session=False)
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()


def test_run_does_not_count_a_failed_stale_refresh_toward_image_blocked(db, city):
    # A failed stale-refresh attempt must NOT share image_fetch_attempts/
    # image_blocked with "this place has no findable images at all" --
    # this place already has a full, valid gallery (that's the only way
    # it became eligible for the stale reserve in the first place). There
    # is no reset path for image_blocked anywhere in this codebase once
    # set, so counting a transient refresh failure (API rate limit,
    # outage) toward it would permanently stop this place from ever
    # refreshing its still-live stale primary again after 3 unlucky runs
    # -- previously it did, since this shared exactly that bookkeeping.
    #
    # place_ids or limit < 2 both bypass the reserve split entirely (see
    # _select_places' early-return) — this needs the real reserve path
    # engaged, so no place_ids and limit=10, same as the test above.
    stale_place = _make_stale_place(db, city)
    db.commit()

    all_ids = [stale_place.id]
    try:
        mock_refresher = MagicMock()
        mock_refresher.refresh_primary.return_value = False

        worker = ImageWorker(stale_refresher=mock_refresher)
        worker.run(db=db, limit=10, force_refresh=False)

        db.refresh(stale_place)
        assert stale_place.image_fetch_attempts == 0
        assert stale_place.image_blocked is False
    finally:
        db.query(PlaceImage).filter(PlaceImage.place_id.in_(all_ids)).delete(synchronize_session=False)
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()


def test_run_still_blocks_a_place_after_repeated_regular_ingest_failures(db, city):
    # Contrast case: the counter/blocking mechanism itself is still very
    # much alive for what it was actually built for -- a place with no
    # findable images at all, going through the normal (non-stale-refresh)
    # ingest path. Only the stale-refresh path is exempted above.
    place = _make_needs_work_place(db, city, rank_score=999.0)
    db.add(place)
    db.commit()

    all_ids = [place.id]
    try:
        mock_ingest_service = MagicMock()
        mock_ingest_service.ingest_place_images.return_value = []

        worker = ImageWorker(ingest_service=mock_ingest_service)
        for _ in range(3):
            worker.run(db=db, limit=1, place_ids=[place.id], force_refresh=False)

        db.refresh(place)
        assert place.image_fetch_attempts == 3
        assert place.image_blocked is True
    finally:
        db.query(PlaceImage).filter(PlaceImage.place_id.in_(all_ids)).delete(synchronize_session=False)
        db.query(Place).filter(Place.id.in_(all_ids)).delete(synchronize_session=False)
        db.commit()
