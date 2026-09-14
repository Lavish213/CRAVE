from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest

from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.session import SessionLocal
from app.services.images.materialize_image_truth import MaterializeImageTruth
from app.services.images.image_ingest_service import ImageIngestService


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
    row = City(
        id=str(uuid.uuid4()),
        slug=f"image-ingest-{suffix}",
        name=f"Image Ingest {suffix}",
        is_active=True,
    )
    db.add(row)
    db.commit()
    yield row
    db.query(City).filter(City.id == row.id).delete()
    db.commit()


def _image(*, primary=False):
    return SimpleNamespace(is_primary=primary)


def test_partial_gallery_is_not_treated_as_complete():
    service = ImageIngestService()

    assert service._has_complete_gallery(
        SimpleNamespace(images=[_image(primary=True)])
    ) is False
    assert service._has_complete_gallery(
        SimpleNamespace(images=[_image(), _image()])
    ) is False


def test_gallery_requires_minimum_count_and_primary_to_skip_ingestion():
    service = ImageIngestService()

    assert service._has_complete_gallery(
        SimpleNamespace(images=[_image(), _image(), _image()])
    ) is False
    assert service._has_complete_gallery(
        SimpleNamespace(images=[_image(primary=True), _image(), _image()])
    ) is True


def test_materialized_images_preserve_source_metadata(db, city):
    place = Place(
        name="Source Metadata Cafe",
        city_id=city.id,
        is_active=True,
    )
    db.add(place)
    db.commit()

    try:
        materializer = MaterializeImageTruth()
        written = materializer.write(
            db=db,
            place=place,
            gallery_payload={
                "primary": {"url": "places/google/photos/abc", "score": 0.91},
                "gallery": [
                    {
                        "url": "places/google/photos/abc",
                        "source": "google",
                        "context": "google_places",
                        "score": 0.91,
                        "metadata": {
                            "photo_reference": "places/google/photos/abc",
                            "html_attributions": ["<a href='https://example.com'>Owner</a>"],
                        },
                    }
                ],
            },
        )
        db.commit()

        assert len(written) == 1
        image = db.query(PlaceImage).filter(PlaceImage.place_id == place.id).one()
        assert image.source_provider == "google"
        assert image.source_context == "google_places"
        assert image.source_metadata == {
            "photo_reference": "places/google/photos/abc",
            "html_attributions": ["<a href='https://example.com'>Owner</a>"],
        }
    finally:
        db.query(PlaceImage).filter(PlaceImage.place_id == place.id).delete()
        db.query(Place).filter(Place.id == place.id).delete()
        db.commit()
