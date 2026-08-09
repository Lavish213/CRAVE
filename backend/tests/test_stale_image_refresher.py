"""
Coverage for app.services.images.stale_image_refresher.StaleImageRefresher —
the durable-storage half of the stale-photo-reference fix in
ImageWorker._select_places' stale-refresh reserve.

Deliberately does NOT go through ImageIngestService's normal gallery-
rebuild pipeline: Google's Places API (New) photo resource names are
session-scoped, so a fresh GoogleImageFetcher.fetch() call for a place
that already has images returns reference strings that won't match
anything already in place_images.url. Running the full pipeline on every
periodic stale-refresh cycle would accumulate a fresh, never-pruned set of
gallery rows every ~30 days instead of just replacing what's stale. These
tests confirm refresh_primary updates the existing primary row in place —
no new PlaceImage rows, ever — and fails closed (leaving the existing
primary untouched) at every stage that can go wrong.
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
from app.services.images.stale_image_refresher import StaleImageRefresher


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
    c = City(slug=f"refresh-test-{suffix}", name=f"Refresh Test City {suffix}")
    db.add(c)
    db.commit()
    yield c
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


@pytest.fixture
def place_with_primary(db, city):
    p = Place(name=f"Place {uuid.uuid4().hex[:8]}", city_id=city.id, is_active=True, rank_score=0.9)
    db.add(p)
    db.flush()
    old_created_at = datetime.now(timezone.utc) - timedelta(days=45)
    primary = PlaceImage(
        place_id=p.id,
        url="places/OLD_STALE_REF/photos/abc123",
        is_primary=True,
    )
    db.add(primary)
    db.flush()
    primary.created_at = old_created_at
    db.commit()
    yield p, primary
    # refresh_primary() mutates `primary` in-memory without committing (by
    # design — ImageWorker.run() owns the commit) — discard that pending
    # state first, or the bulk delete() below (a raw DELETE that doesn't
    # autoflush) leaves a dangling UPDATE that fails at commit time with
    # StaleDataError once its target row is already gone.
    db.rollback()
    db.query(PlaceImage).filter(PlaceImage.place_id == p.id).delete(synchronize_session=False)
    db.query(Place).filter(Place.id == p.id).delete(synchronize_session=False)
    db.commit()


def _refresher(*, fetch_return=None, download_return=(b"bytes", "image/jpeg"), upload_side_effect=None):
    fetcher = MagicMock()
    fetcher.fetch.return_value = fetch_return if fetch_return is not None else [
        {"url": "places/FRESH_REF/photos/xyz789"}
    ]

    download_fn = MagicMock(return_value=download_return)

    upload_fn = MagicMock(side_effect=upload_side_effect)

    public_url_fn = MagicMock(return_value="https://bucket.example.r2.cloudflarestorage.com/google-photos/key.jpg")

    return StaleImageRefresher(
        fetcher=fetcher,
        download_fn=download_fn,
        upload_fn=upload_fn,
        public_url_fn=public_url_fn,
    ), fetcher, download_fn, upload_fn, public_url_fn


def test_refresh_primary_updates_existing_row_in_place_on_success(db, place_with_primary):
    place, primary = place_with_primary
    refresher, fetcher, download_fn, upload_fn, public_url_fn = _refresher()

    ok = refresher.refresh_primary(db=db, place=place)

    assert ok is True
    assert primary.url == "https://bucket.example.r2.cloudflarestorage.com/google-photos/key.jpg"
    # Staleness clock reset — this is what makes _stale_primary_clause stop
    # selecting this place again until it's genuinely old once more.
    assert primary.created_at > datetime.now(timezone.utc) - timedelta(minutes=1)

    # No new gallery rows — the whole point of not going through the
    # normal ingest pipeline for this path.
    all_images = db.query(PlaceImage).filter(PlaceImage.place_id == place.id).all()
    assert len(all_images) == 1
    assert all_images[0].id == primary.id

    fetcher.fetch.assert_called_once_with(place=place)
    download_fn.assert_called_once_with("places/FRESH_REF/photos/xyz789")
    upload_fn.assert_called_once()


def test_refresh_primary_returns_false_and_leaves_row_untouched_when_no_candidates(db, place_with_primary):
    place, primary = place_with_primary
    original_url = primary.url
    original_created_at = primary.created_at
    refresher, *_ = _refresher(fetch_return=[])

    ok = refresher.refresh_primary(db=db, place=place)

    assert ok is False
    assert primary.url == original_url
    assert primary.created_at == original_created_at


def test_refresh_primary_returns_false_when_download_fails(db, place_with_primary):
    place, primary = place_with_primary
    original_url = primary.url
    refresher, *_ = _refresher(download_return=None)

    ok = refresher.refresh_primary(db=db, place=place)

    assert ok is False
    assert primary.url == original_url


def test_refresh_primary_returns_false_when_upload_raises(db, place_with_primary):
    place, primary = place_with_primary
    original_url = primary.url
    refresher, *_ = _refresher(upload_side_effect=RuntimeError("R2 is down"))

    ok = refresher.refresh_primary(db=db, place=place)

    assert ok is False
    assert primary.url == original_url


def test_refresh_primary_returns_false_when_place_has_no_primary_image(db, city):
    p = Place(name=f"Place {uuid.uuid4().hex[:8]}", city_id=city.id, is_active=True)
    db.add(p)
    db.commit()
    refresher, fetcher, *_ = _refresher()

    try:
        ok = refresher.refresh_primary(db=db, place=p)
        assert ok is False
        fetcher.fetch.assert_not_called()
    finally:
        db.query(Place).filter(Place.id == p.id).delete(synchronize_session=False)
        db.commit()
