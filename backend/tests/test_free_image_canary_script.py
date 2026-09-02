from types import SimpleNamespace
import uuid

import pytest

from app.db.models.city import City
from app.db.models.place import Place
from app.db.session import SessionLocal

from scripts.run_free_image_canary import (
    FreeOnlyImageReader,
    build_preview,
    parse_place_ids,
    run_is_authorized,
    stage_canary,
)


def test_parse_place_ids_dedupes_in_order():
    assert parse_place_ids("a,b\na") == ["a", "b"]


def test_confirmation_must_match_exactly():
    assert run_is_authorized(requested_count=2, confirm_count=2)
    assert not run_is_authorized(requested_count=2, confirm_count=1)
    assert not run_is_authorized(requested_count=2, confirm_count=None)


def test_free_reader_never_calls_google(monkeypatch):
    reader = FreeOnlyImageReader()
    monkeypatch.setattr(reader, "_read_provider", lambda place: [])
    monkeypatch.setattr(reader, "_read_website", lambda place, db=None: [])
    monkeypatch.setattr(reader, "_read_google", lambda place: (_ for _ in ()).throw(AssertionError()))
    assert reader.read(place=SimpleNamespace(id="p1"), db=None) == []


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def city(db):
    suffix = uuid.uuid4().hex[:8]
    value = City(name=f"Free Image Canary {suffix}", slug=f"free-image-{suffix}", is_active=True)
    db.add(value)
    db.commit()
    return value


def make_place(db, city, *, place_id: str) -> Place:
    place = Place(
        id=place_id,
        name=f"Place {place_id}",
        city_id=city.id,
        website="https://example.com",
        is_active=True,
    )
    db.add(place)
    db.commit()
    return place


def test_preview_reports_existing_rows(db, city):
    from app.db.models.place_image import PlaceImage

    place = make_place(db, city, place_id=str(uuid.uuid4()))
    db.add(PlaceImage(place_id=place.id, url="https://example.com/photo.jpg"))
    db.commit()

    summary, rows, _ = build_preview(db, [place.id, "missing"])

    assert summary["missing"] == ["missing"]
    assert summary["already_has_image_rows"] == [place.id]
    assert rows[0]["existing_image_rows"] == 1


def test_stage_canary_hides_every_new_image(db, city, monkeypatch):
    from app.db.models.place_image import PlaceImage, VISIBILITY_HIDDEN
    from scripts import run_free_image_canary as module

    place = make_place(db, city, place_id=str(uuid.uuid4()))

    def fake_ingest(self, *, db, place, force_refresh=False):
        image = PlaceImage(
            place_id=place.id,
            url="https://example.com/food.jpg",
            is_primary=True,
        )
        db.add(image)
        return [image]

    monkeypatch.setattr(module.ImageIngestService, "ingest_place_images", fake_ingest)

    results, summary = stage_canary(
        db,
        place_ids=[place.id],
        places_by_id={place.id: place},
    )

    image = db.query(PlaceImage).filter(PlaceImage.place_id == place.id).one()
    assert image.visibility_status == VISIBILITY_HIDDEN
    assert image.is_primary is False
    assert results[0]["staged"] == 1
    assert summary == {"attempted": 1, "staged": 1, "publicly_visible": 0}
