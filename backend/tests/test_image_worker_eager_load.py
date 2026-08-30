"""
Regression test for the same bug class caught in
test_recompute_scores_worker_city_lookup.py: Place.images and Place.claims
were changed from lazy="selectin" to lazy="select" after a whole-app grep
found "zero real usages" -- but ImageIngestService._has_complete_gallery()
reads place.images, and ProviderImageExtractor._provider_payloads() (via
ImageReader, reached from the same ingest_place_images() pipeline) reads
place.claims, both via getattr(place, "...", default) rather than literal
dot-access, which is what the earlier grep missed.

app/workers/image_worker.py::ImageWorker._select_places() is the query
every scheduled image_ingestion run (up to 100 places, every ~5 minutes)
uses to build the places list later passed into ingest_place_images() for
each place in a loop -- so an unloaded images/claims relationship there
means one extra query per place, every run.

Fixed by adding .options(selectinload(Place.images), selectinload(Place.claims))
to both select(Place) statements inside _select_places(). This checks the
returned Place objects directly via SQLAlchemy's own inspection API
(unloaded attribute set) rather than running the full ingestion pipeline,
which makes real outbound HTTP calls (Google Places photos, website
scraping) and isn't something a unit test should trigger.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import inspect

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
    c = City(slug=f"eager-load-test-{suffix}", name=f"Eager Load Test City {suffix}")
    db.add(c)
    db.commit()
    yield c
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_place(db, city) -> Place:
    p = Place(name=f"Eager Load Test Place {uuid.uuid4().hex[:8]}", city_id=city.id, is_active=True)
    db.add(p)
    db.commit()
    return p


def test_select_places_eagerly_loads_images_and_claims(db, city):
    place = _make_place(db, city)
    place_id = place.id

    # Fresh session (empty identity map) -- mirrors the real scheduler job,
    # which always starts from a brand-new SessionLocal().
    fresh_db = SessionLocal()
    try:
        worker = ImageWorker()
        places, _stale_ids = worker._select_places(
            db=fresh_db, limit=10, force_refresh=True, place_ids=[place_id],
        )
        assert len(places) == 1

        unloaded = inspect(places[0]).unloaded
        assert "images" not in unloaded, (
            "place.images was not eagerly loaded -- "
            "ImageIngestService._has_complete_gallery() would issue an "
            "extra query per place instead of using the batch fetch"
        )
        assert "claims" not in unloaded, (
            "place.claims was not eagerly loaded -- "
            "ProviderImageExtractor._provider_payloads() would issue an "
            "extra query per place instead of using the batch fetch"
        )
    finally:
        fresh_db.close()
        db.query(Place).filter(Place.id == place_id).delete()
        db.commit()
