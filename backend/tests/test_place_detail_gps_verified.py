"""
Coverage for image_gps_verified on GET /api/v1/place/{place_id}.

gps_verified was computed and stored on PlaceImage at upload time (see
app/services/images/upload_moderation.py) but no endpoint ever returned
it — the "this photo was actually taken here" signal existed only in the
database, invisible to the person it was meant to reassure. Index-aligned
with images/image_ids, same pattern as image_ids itself.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage, VISIBILITY_SHOWCASE

client = TestClient(app)


def _make_place_with_images(*, gps_flags: list[bool]) -> str:
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        city = City(
            id=str(uuid.uuid4()), name="GPS Badge Test City",
            slug=f"gps-badge-test-{suffix}", lat=37.8, lng=-122.27, is_active=True,
        )
        db.add(city)
        db.flush()

        place = Place(name="GPS Badge Test Place", city_id=city.id, is_active=True)
        db.add(place)
        db.flush()

        for i, verified in enumerate(gps_flags):
            db.add(PlaceImage(
                place_id=place.id,
                url=f"https://example.com/{i}.jpg",
                is_primary=(i == 0),
                visibility_status=VISIBILITY_SHOWCASE,
                gps_verified=verified,
            ))

        db.commit()
        return place.id
    finally:
        db.close()


def test_gps_verified_flags_are_index_aligned_with_images():
    place_id = _make_place_with_images(gps_flags=[True, False])

    response = client.get(f"/api/v1/place/{place_id}")

    assert response.status_code == 200
    body = response.json()
    assert len(body["image_gps_verified"]) == len(body["images"])
    assert len(body["image_gps_verified"]) == len(body["image_ids"])


def test_gps_verified_photo_reports_true():
    place_id = _make_place_with_images(gps_flags=[True])

    body = client.get(f"/api/v1/place/{place_id}").json()

    assert body["image_gps_verified"] == [True]


def test_unverified_photo_reports_false_not_missing():
    place_id = _make_place_with_images(gps_flags=[False])

    body = client.get(f"/api/v1/place/{place_id}").json()

    assert body["image_gps_verified"] == [False]


def test_place_with_no_images_returns_empty_list_not_error():
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        city = City(
            id=str(uuid.uuid4()), name="No Photos Test City",
            slug=f"no-photos-test-{suffix}", lat=37.8, lng=-122.27, is_active=True,
        )
        db.add(city)
        db.flush()
        place = Place(name="No Photos Test Place", city_id=city.id, is_active=True)
        db.add(place)
        db.commit()
        place_id = place.id
    finally:
        db.close()

    response = client.get(f"/api/v1/place/{place_id}")

    assert response.status_code == 200
    assert response.json()["image_gps_verified"] == []
