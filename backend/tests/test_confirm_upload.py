"""
Coverage for app.services.upload.upload_service.confirm_upload's two guards.

Confirmed real bug found via a bug-hunting review pass: confirm_upload had
no ownership check (any authenticated user could confirm any image_id --
image_ids are public, returned by GET /place/{id} for every place's
gallery) and unconditionally forced status back to "processing" even when
an image was already "ready". Re-confirming an already-ready image
re-triggers process_image_upload(), which re-hashes the image and runs it
through app/services/upload/dedup.py's is_duplicate_image() -- whose
exact-match query has no way to exclude the image's own existing row, so
it matches itself as a "duplicate" and permanently marks an already-
published photo status="failed". process_image_upload() itself already
refuses to touch anything not in ("processing", "pending") -- the entire
hole existed only because confirm_upload was blindly forcing status back
into that set regardless of where it already was.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.services.upload.upload_service import confirm_upload, UploadForbiddenError


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def place(db):
    suffix = uuid.uuid4().hex[:8]
    c = City(slug=f"confirm-upload-test-{suffix}", name=f"Confirm Upload Test City {suffix}")
    db.add(c)
    db.commit()
    p = Place(name=f"Place {suffix}", city_id=c.id, is_active=True, rank_score=1.0)
    db.add(p)
    db.commit()
    yield p
    db.query(PlaceImage).filter(PlaceImage.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_image(db, place, *, status: str, uploaded_by: str, phash: str | None = None) -> PlaceImage:
    img = PlaceImage(
        place_id=place.id,
        uploaded_by=uploaded_by,
        status=status,
        phash=phash,
    )
    db.add(img)
    db.commit()
    return img


def test_confirms_a_pending_upload_owned_by_the_caller(db, place):
    img = _make_image(db, place, status="pending", uploaded_by="user-a")

    transitioned = confirm_upload(db, image_id=img.id, user_id="user-a")

    assert transitioned is True
    db.refresh(img)
    assert img.status == "processing"


def test_rejects_confirmation_by_a_user_who_does_not_own_the_upload(db, place):
    img = _make_image(db, place, status="pending", uploaded_by="user-a")

    with pytest.raises(UploadForbiddenError):
        confirm_upload(db, image_id=img.id, user_id="user-b")

    db.refresh(img)
    # Must not have been mutated by the rejected attempt.
    assert img.status == "pending"


def test_reconfirming_an_already_ready_image_is_a_no_op_not_a_reprocess(db, place):
    # This is the actual data-loss bug: without the status guard, this
    # call would force status back to "processing", making the caller
    # believe a second process_image_upload() run is safe -- which then
    # dedup-matches the image against its own stored phash and marks an
    # already-published photo "failed".
    img = _make_image(db, place, status="ready", uploaded_by="user-a", phash="abc123")

    transitioned = confirm_upload(db, image_id=img.id, user_id="user-a")

    assert transitioned is False
    db.refresh(img)
    assert img.status == "ready"


def test_reconfirming_a_failed_image_is_also_a_no_op(db, place):
    img = _make_image(db, place, status="failed", uploaded_by="user-a")

    transitioned = confirm_upload(db, image_id=img.id, user_id="user-a")

    assert transitioned is False
    db.refresh(img)
    assert img.status == "failed"


def test_missing_image_raises_value_error(db):
    with pytest.raises(ValueError):
        confirm_upload(db, image_id=str(uuid.uuid4()), user_id="user-a")
