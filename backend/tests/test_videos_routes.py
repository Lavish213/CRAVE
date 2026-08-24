"""
End-to-end HTTP coverage for app/api/v1/routes/videos.py -- confirms
actual wiring (registration, request/response shapes, auth plumbing), not
just the service-layer logic already covered in
test_video_upload_service.py and test_video_processing_worker.py.
"""
from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.user_auth import get_current_user_id
from app.core.rate_limit import rate_limit
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_video import PlaceVideo, STATUS_APPROVED
from app.db.models.video_template import VideoTemplate

client = TestClient(app)


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides():
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(rate_limit, None)


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
    c = City(slug=f"video-route-test-{suffix}", name=f"Video Route Test City {suffix}")
    db.add(c)
    db.commit()
    p = Place(name=f"Video Route Test Place {suffix}", city_id=c.id, is_active=True)
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
    ):
        yield


def test_request_and_confirm_roundtrip(place):
    _as_user("route-test-alice")

    resp = client.post(
        "/api/v1/videos/request",
        json={"place_id": place.id, "content_type": "video/mp4"},
    )
    assert resp.status_code == 200
    video_id = resp.json()["video_id"]
    assert resp.json()["upload_url"] == "https://r2.example.test/signed-put-url"

    with patch(
        "app.services.video.video_upload_service.head_object",
        return_value={"ContentLength": 1024},
    ):
        confirm_resp = client.post(f"/api/v1/videos/{video_id}/confirm")
    assert confirm_resp.status_code == 200
    assert confirm_resp.json() == {"ok": True}

    status_resp = client.get(f"/api/v1/videos/{video_id}")
    assert status_resp.status_code == 200
    assert status_resp.json()["status"] == "queued"


def test_confirm_is_forbidden_for_a_different_user(place):
    _as_user("route-test-alice")
    video_id = client.post(
        "/api/v1/videos/request",
        json={"place_id": place.id, "content_type": "video/mp4"},
    ).json()["video_id"]

    _as_user("route-test-bob")
    resp = client.post(f"/api/v1/videos/{video_id}/confirm")

    assert resp.status_code == 403


def test_status_is_forbidden_for_a_different_user(place):
    _as_user("route-test-alice")
    video_id = client.post(
        "/api/v1/videos/request",
        json={"place_id": place.id, "content_type": "video/mp4"},
    ).json()["video_id"]

    _as_user("route-test-bob")
    resp = client.get(f"/api/v1/videos/{video_id}")

    assert resp.status_code == 403


def test_status_404s_for_a_nonexistent_video():
    _as_user("route-test-alice")
    resp = client.get(f"/api/v1/videos/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_request_400s_for_an_unknown_place():
    _as_user("route-test-alice")
    resp = client.post(
        "/api/v1/videos/request",
        json={"place_id": str(uuid.uuid4()), "content_type": "video/mp4"},
    )
    assert resp.status_code == 400


def test_feed_returns_only_approved_videos_for_the_place(db, place):
    approved = PlaceVideo(
        place_id=place.id, uploaded_by="route-test-alice",
        status=STATUS_APPROVED, processed_key="places/x/videos/processed/a.mp4",
        thumb_key="places/x/videos/thumbs/a.jpg",
    )
    pending = PlaceVideo(place_id=place.id, uploaded_by="route-test-alice", status="pending")
    db.add_all([approved, pending])
    db.commit()

    resp = client.get(f"/api/v1/videos/feed?place_id={place.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["videos"]) == 1
    assert body["videos"][0]["id"] == approved.id


def test_templates_lists_only_active_ones_ordered(db):
    suffix = uuid.uuid4().hex[:8]
    active = VideoTemplate(id=f"active-{suffix}", name="Active", beat_cues=[], sort_order=1)
    inactive = VideoTemplate(id=f"inactive-{suffix}", name="Inactive", beat_cues=[], active=False, sort_order=0)
    db.add_all([active, inactive])
    db.commit()

    resp = client.get("/api/v1/videos/templates")

    assert resp.status_code == 200
    ids = [t["id"] for t in resp.json()["templates"]]
    assert active.id in ids
    assert inactive.id not in ids

    db.query(VideoTemplate).filter(VideoTemplate.id.in_([active.id, inactive.id])).delete(
        synchronize_session=False
    )
    db.commit()
