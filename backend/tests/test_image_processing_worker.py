"""
Coverage for app.workers.image_processing_worker.process_image_upload —
specifically the primary-image election fix.

Before this fix: a successfully-processed user upload always landed with
is_primary=False, visibility_status="gallery_only" (PlaceImage's column
defaults) — it would show in the place-detail gallery but never as the
feed card / map pin thumbnail, both of which only ever query
is_primary=True. Worse, ImageIngestService.ingest_place_images skips a
place entirely the moment it has *any* image (see
_has_existing_images), and the scheduled ImageWorker never passes
force_refresh=True. So a place whose first-ever photo came from a user
upload would never get a primary image from any source — the card/pin
stays on the empty-state fallback forever despite a real photo existing.

The S3 client and the real network/DB boundary (R2) are mocked; PIL
image processing runs for real against a tiny in-memory JPEG so the
actual resize/hash/dedup code path is genuinely exercised, not stubbed.
"""
from __future__ import annotations

import io
import sys
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from PIL import Image

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_CANDIDATE_PRIMARY,
    VISIBILITY_SHOWCASE,
)
import app.workers.image_processing_worker as worker_module
from app.workers.image_processing_worker import process_image_upload


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_place(db) -> Place:
    city = City(
        id=str(uuid.uuid4()), name="Image Worker Test City",
        slug=f"image-worker-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.flush()
    place = Place(name="Image Worker Test Place", city_id=city.id, is_active=True)
    db.add(place)
    db.commit()
    return place


def _make_pending_upload(db, place, **overrides) -> PlaceImage:
    image = PlaceImage(
        id=str(uuid.uuid4()),
        place_id=place.id,
        orig_key=f"places/{place.id}/orig/{uuid.uuid4()}.jpg",
        processed_key=f"places/{place.id}/processed/{uuid.uuid4()}.jpg",
        thumb_key=f"places/{place.id}/thumb/{uuid.uuid4()}.jpg",
        status="processing",
        uploaded_by="test-user",
    )
    for k, v in overrides.items():
        setattr(image, k, v)
    db.add(image)
    db.commit()
    return image


def _jpeg_bytes(color=(200, 100, 50)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color=color).save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture()
def fake_s3():
    """A fake boto3 S3 client: get_object returns a real tiny JPEG,
    put_object is a no-op recorder."""
    client = MagicMock()
    client.get_object.return_value = {"Body": io.BytesIO(_jpeg_bytes())}
    return client


@pytest.fixture(autouse=True)
def _no_dedup(monkeypatch):
    # Dedup is a separate concern from primary election; keep it out of
    # the way unless a specific test wants to exercise it.
    monkeypatch.setattr(worker_module, "is_duplicate_image", lambda *a, **kw: False)


def test_first_upload_for_a_place_becomes_primary(db, fake_s3):
    place = _make_place(db)
    image = _make_pending_upload(db, place)

    with patch.object(worker_module, "_get_s3_client", return_value=fake_s3):
        process_image_upload(image.id)

    db.refresh(image)
    assert image.status == "ready"
    assert image.is_primary is True
    assert image.visibility_status == VISIBILITY_SHOWCASE
    assert image.url is not None
    # A real photo of the place is higher-trust than the neutral 0.5
    # default — see _USER_UPLOAD_CONFIDENCE's module-level comment.
    assert image.confidence == worker_module._USER_UPLOAD_CONFIDENCE


def test_upload_does_not_displace_an_existing_primary(db, fake_s3):
    place = _make_place(db)
    existing_primary = PlaceImage(
        place_id=place.id, url="https://example.com/existing.jpg",
        is_primary=True, visibility_status=VISIBILITY_SHOWCASE, confidence=0.9,
    )
    db.add(existing_primary)
    db.commit()

    image = _make_pending_upload(db, place)

    with patch.object(worker_module, "_get_s3_client", return_value=fake_s3):
        process_image_upload(image.id)

    db.refresh(image)
    db.refresh(existing_primary)

    assert image.status == "ready"
    # Must not have silently taken over primary from an existing image...
    assert image.is_primary is False
    # ...but it's a real contender for it, not generic gallery filler —
    # marked candidate_primary rather than left at the "gallery_only" default.
    assert image.visibility_status == VISIBILITY_CANDIDATE_PRIMARY
    assert image.confidence == worker_module._USER_UPLOAD_CONFIDENCE
    assert existing_primary.is_primary is True


def test_second_upload_for_the_same_place_does_not_also_become_primary(db, fake_s3):
    place = _make_place(db)
    first = _make_pending_upload(db, place)

    with patch.object(worker_module, "_get_s3_client", return_value=fake_s3):
        process_image_upload(first.id)

    second = _make_pending_upload(db, place)
    with patch.object(worker_module, "_get_s3_client", return_value=fake_s3):
        process_image_upload(second.id)

    db.refresh(first)
    db.refresh(second)

    assert first.is_primary is True
    assert second.is_primary is False

    primary_count = (
        db.query(PlaceImage)
        .filter(PlaceImage.place_id == place.id, PlaceImage.is_primary.is_(True))
        .count()
    )
    assert primary_count == 1


def test_invariant_repair_failure_does_not_undo_a_successful_upload(db, fake_s3, monkeypatch):
    place = _make_place(db)
    image = _make_pending_upload(db, place)

    monkeypatch.setattr(
        worker_module.PlaceImageInvariantService, "repair",
        lambda self, *, db, place_id: (_ for _ in ()).throw(RuntimeError("repair blew up")),
    )

    with patch.object(worker_module, "_get_s3_client", return_value=fake_s3):
        process_image_upload(image.id)

    db.refresh(image)
    # The repair() call is defensive housekeeping, not load-bearing — its
    # failure must not roll back or reclassify an upload that already
    # committed successfully.
    assert image.status == "ready"
    assert image.is_primary is True


def test_failed_upload_is_not_promoted_to_primary(db):
    place = _make_place(db)
    image = _make_pending_upload(db, place)

    with patch.object(worker_module, "_get_s3_client", side_effect=RuntimeError("R2 unreachable")):
        process_image_upload(image.id)

    db.refresh(image)
    assert image.status == "failed"
    assert image.is_primary is False
