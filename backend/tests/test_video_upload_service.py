"""
Coverage for app.services.video.video_upload_service -- the request/confirm
flow for the short food-video feature. Applies the same two ownership/
status-guard lessons already fixed in app.services.upload.upload_service's
confirm_upload earlier this review pass, plus the client_id idempotent-
retry path the offline record flow depends on.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_video import PlaceVideo, STATUS_PENDING, STATUS_QUEUED, STATUS_REJECTED
from app.db.models.video_template import VideoTemplate
from app.services.video.video_upload_service import (
    request_video_upload_slot,
    confirm_video_upload,
    UploadForbiddenError,
)


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
    c = City(slug=f"video-upload-test-{suffix}", name=f"Video Upload Test City {suffix}")
    db.add(c)
    db.commit()
    p = Place(name=f"Place {suffix}", city_id=c.id, is_active=True)
    db.add(p)
    db.commit()
    yield p
    db.query(PlaceVideo).filter(PlaceVideo.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


@pytest.fixture(autouse=True)
def _mock_presign():
    with patch(
        "app.services.video.video_upload_service.generate_presigned_upload_url",
        return_value="https://r2.example.test/signed-put-url",
    ) as mocked:
        yield mocked


def test_request_upload_slot_creates_pending_video(db, place):
    result = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
    )

    assert result["upload_url"] == "https://r2.example.test/signed-put-url"
    video = db.query(PlaceVideo).filter(PlaceVideo.id == result["video_id"]).one()
    assert video.status == STATUS_PENDING
    assert video.uploaded_by == "user-a"
    assert video.orig_key.endswith(".mp4")


def test_request_upload_slot_rejects_unsupported_content_type(db, place):
    with pytest.raises(ValueError):
        request_video_upload_slot(
            db, place_id=place.id, content_type="video/x-msvideo", uploaded_by="user-a",
        )


def test_request_upload_slot_rejects_unknown_place(db):
    with pytest.raises(ValueError):
        request_video_upload_slot(
            db, place_id=str(uuid.uuid4()), content_type="video/mp4", uploaded_by="user-a",
        )


def test_request_upload_slot_rejects_unknown_template(db, place):
    with pytest.raises(ValueError):
        request_video_upload_slot(
            db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
            template_id="not-a-real-template",
        )


def test_request_upload_slot_accepts_active_template(db, place):
    template = VideoTemplate(id=f"tmpl-{uuid.uuid4().hex[:6]}", name="Test Template", beat_cues=[])
    db.add(template)
    db.commit()

    result = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
        template_id=template.id,
    )
    video = db.query(PlaceVideo).filter(PlaceVideo.id == result["video_id"]).one()
    assert video.template_id == template.id

    db.query(VideoTemplate).filter(VideoTemplate.id == template.id).delete()
    db.commit()


def test_repeated_request_with_same_client_id_reuses_the_row(db, place):
    client_id = f"client-{uuid.uuid4().hex[:8]}"

    first = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
        client_id=client_id,
    )
    second = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
        client_id=client_id,
    )

    assert first["video_id"] == second["video_id"]
    count = db.query(PlaceVideo).filter(PlaceVideo.client_id == client_id).count()
    assert count == 1


def test_repeated_request_with_same_client_id_from_a_different_user_is_forbidden(db, place):
    client_id = f"client-{uuid.uuid4().hex[:8]}"
    request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
        client_id=client_id,
    )

    with pytest.raises(UploadForbiddenError):
        request_video_upload_slot(
            db, place_id=place.id, content_type="video/mp4", uploaded_by="user-b",
            client_id=client_id,
        )


def test_confirm_transitions_pending_to_queued(db, place):
    result = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
    )

    with patch(
        "app.services.video.video_upload_service.head_object",
        return_value={"ContentLength": 1024},
    ):
        transitioned = confirm_video_upload(db, video_id=result["video_id"], user_id="user-a")

    assert transitioned is True
    video = db.query(PlaceVideo).filter(PlaceVideo.id == result["video_id"]).one()
    assert video.status == STATUS_QUEUED


def test_confirm_rejects_a_different_owner(db, place):
    result = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
    )

    with pytest.raises(UploadForbiddenError):
        confirm_video_upload(db, video_id=result["video_id"], user_id="user-b")

    video = db.query(PlaceVideo).filter(PlaceVideo.id == result["video_id"]).one()
    assert video.status == STATUS_PENDING


def test_reconfirming_an_already_queued_video_is_a_no_op(db, place):
    result = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
    )
    with patch(
        "app.services.video.video_upload_service.head_object",
        return_value={"ContentLength": 1024},
    ):
        confirm_video_upload(db, video_id=result["video_id"], user_id="user-a")
        transitioned = confirm_video_upload(db, video_id=result["video_id"], user_id="user-a")

    assert transitioned is False


def test_confirm_missing_upload_raises(db, place):
    result = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
    )

    with patch(
        "app.services.video.video_upload_service.head_object",
        side_effect=Exception("NoSuchKey"),
    ):
        with pytest.raises(ValueError):
            confirm_video_upload(db, video_id=result["video_id"], user_id="user-a")


def test_confirm_rejects_an_oversized_upload(db, place):
    result = request_video_upload_slot(
        db, place_id=place.id, content_type="video/mp4", uploaded_by="user-a",
    )

    oversized_bytes = (100 * 1024 * 1024) + 1  # comfortably over the 50MB default cap
    with patch(
        "app.services.video.video_upload_service.head_object",
        return_value={"ContentLength": oversized_bytes},
    ), patch("app.services.video.video_upload_service.delete_object") as mock_delete:
        with pytest.raises(ValueError, match="exceeds max upload size"):
            confirm_video_upload(db, video_id=result["video_id"], user_id="user-a")

    mock_delete.assert_called_once()
    video = db.query(PlaceVideo).filter(PlaceVideo.id == result["video_id"]).one()
    assert video.status == STATUS_REJECTED
