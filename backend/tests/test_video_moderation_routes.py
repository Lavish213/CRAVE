"""
Coverage for the video report + review-queue endpoints added to
app/api/v1/routes/moderation.py — same shape as test_moderation_routes.py's
image coverage, since video reuses that exact pattern (see
place_video.py's moderation_status/moderation_reason comment for why this
is a separate axis from PlaceVideo.status).
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.video_report import AUTO_HIDE_REPORT_COUNT, VideoReport
from app.db.models.place_video import (
    PlaceVideo,
    STATUS_APPROVED,
    MOD_APPROVED,
    MOD_PENDING_REVIEW,
    MOD_REJECTED,
)

client = TestClient(app)

ADMIN_ID = "video-moderation-admin-fixture"


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    app.dependency_overrides[rate_limit] = lambda: None
    monkeypatch.setenv("ADMIN_USER_IDS", ADMIN_ID)
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
def video(db):
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"vidmodroute-{suffix}", name=f"VidModRoute City {suffix}")
    db.add(city)
    db.flush()
    place = Place(name=f"VidModRoute Place {suffix}", city_id=city.id)
    db.add(place)
    db.flush()
    vid = PlaceVideo(
        place_id=place.id,
        uploaded_by="uploader-1",
        processed_key=f"videos/{suffix}/processed.mp4",
        thumb_key=f"videos/{suffix}/thumb.jpg",
        status=STATUS_APPROVED,
        moderation_status=MOD_APPROVED,
    )
    db.add(vid)
    db.commit()

    yield vid

    db.query(VideoReport).filter(VideoReport.video_id == vid.id).delete()
    db.query(PlaceVideo).filter(PlaceVideo.place_id == place.id).delete()
    db.query(Place).filter(Place.id == place.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def test_reporting_a_video_records_it(db, video):
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/videos/{video.id}/report",
        json={"reason": "inappropriate"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "reported"

    assert db.query(VideoReport).filter(VideoReport.video_id == video.id).count() == 1


def test_a_single_report_does_not_hide_the_video(db, video):
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/videos/{video.id}/report", json={"reason": "spam"},
    )
    assert resp.json()["withheld"] is False

    db.refresh(video)
    assert video.moderation_status == MOD_APPROVED


def test_same_user_reporting_twice_is_idempotent(db, video):
    _as_user("reporter-a")
    first = client.post(
        f"/api/v1/moderation/videos/{video.id}/report", json={"reason": "spam"},
    )
    second = client.post(
        f"/api/v1/moderation/videos/{video.id}/report", json={"reason": "spam"},
    )

    assert first.status_code == 201
    assert second.json()["status"] == "already_reported"
    assert db.query(VideoReport).filter(VideoReport.video_id == video.id).count() == 1


def test_enough_distinct_reports_withholds_the_video(db, video):
    for i in range(AUTO_HIDE_REPORT_COUNT):
        _as_user(f"reporter-{i}")
        resp = client.post(
            f"/api/v1/moderation/videos/{video.id}/report",
            json={"reason": "inappropriate"},
        )

    assert resp.json()["withheld"] is True

    db.refresh(video)
    assert video.moderation_status == MOD_PENDING_REVIEW
    assert video.moderation_reason == "user_reported"
    # Processing status is untouched — this is a moderation decision, not
    # a pipeline outcome.
    assert video.status == STATUS_APPROVED


def test_auto_hide_holds_for_review_rather_than_deleting(db, video):
    for i in range(AUTO_HIDE_REPORT_COUNT):
        _as_user(f"reporter-{i}")
        client.post(
            f"/api/v1/moderation/videos/{video.id}/report", json={"reason": "spam"},
        )

    db.refresh(video)
    assert video.moderation_status == MOD_PENDING_REVIEW
    assert video.moderation_status != MOD_REJECTED
    assert db.query(PlaceVideo).filter(PlaceVideo.id == video.id).count() == 1


def test_invalid_reason_is_rejected(video):
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/videos/{video.id}/report", json={"reason": "i_dislike_it"},
    )
    assert resp.status_code == 400


def test_reporting_unknown_video_404s():
    _as_user("reporter-a")
    resp = client.post(
        "/api/v1/moderation/videos/does-not-exist/report", json={"reason": "spam"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Review queue — admin gated
# ---------------------------------------------------------------------------

def test_queue_is_invisible_to_non_admins(video):
    _as_user("ordinary-user")
    assert client.get("/api/v1/moderation/videos/queue").status_code == 404


def test_queue_fails_closed_when_no_admins_configured(monkeypatch, video):
    monkeypatch.setenv("ADMIN_USER_IDS", "")
    _as_user(ADMIN_ID)
    assert client.get("/api/v1/moderation/videos/queue").status_code == 404


def test_queue_lists_pending_videos_with_their_signals(db, video):
    video.moderation_status = MOD_PENDING_REVIEW
    video.moderation_reason = "user_reported"
    video.food_score = 0.9
    db.commit()

    _as_user(ADMIN_ID)
    resp = client.get("/api/v1/moderation/videos/queue")

    assert resp.status_code == 200
    row = next(r for r in resp.json()["queue"] if r["video_id"] == video.id)
    assert row["moderation_reason"] == "user_reported"
    assert row["food_score"] == 0.9
    assert row["report_count"] == 0


def test_queue_excludes_already_approved_videos(db, video):
    _as_user(ADMIN_ID)
    ids = [r["video_id"] for r in client.get("/api/v1/moderation/videos/queue").json()["queue"]]
    assert video.id not in ids


def test_queue_reports_the_report_count(db, video):
    for i in range(2):
        _as_user(f"reporter-{i}")
        client.post(
            f"/api/v1/moderation/videos/{video.id}/report", json={"reason": "spam"},
        )
    video.moderation_status = MOD_PENDING_REVIEW
    db.commit()

    _as_user(ADMIN_ID)
    row = next(
        r for r in client.get("/api/v1/moderation/videos/queue").json()["queue"]
        if r["video_id"] == video.id
    )
    assert row["report_count"] == 2


# ---------------------------------------------------------------------------
# Resolving a review
# ---------------------------------------------------------------------------

def test_approving_clears_moderation_reason(db, video):
    video.moderation_status = MOD_PENDING_REVIEW
    video.moderation_reason = "user_reported"
    db.commit()

    _as_user(ADMIN_ID)
    resp = client.post(
        f"/api/v1/moderation/videos/{video.id}/review", json={"decision": "approve"},
    )
    assert resp.status_code == 200

    db.refresh(video)
    assert video.moderation_status == MOD_APPROVED
    assert video.moderation_reason is None
    assert video.reviewed_by == ADMIN_ID
    assert video.reviewed_at is not None


def test_rejecting_hides_the_video_from_feed(db, video):
    video.moderation_status = MOD_PENDING_REVIEW
    db.commit()

    _as_user(ADMIN_ID)
    client.post(
        f"/api/v1/moderation/videos/{video.id}/review", json={"decision": "reject"},
    )

    db.refresh(video)
    assert video.moderation_status == MOD_REJECTED

    resp = client.get("/api/v1/videos/feed", params={"place_id": video.place_id})
    ids = [v["id"] for v in resp.json()["videos"]]
    assert video.id not in ids


def test_review_requires_admin(db, video):
    video.moderation_status = MOD_PENDING_REVIEW
    db.commit()

    _as_user("ordinary-user")
    resp = client.post(
        f"/api/v1/moderation/videos/{video.id}/review", json={"decision": "approve"},
    )
    assert resp.status_code == 404

    db.refresh(video)
    assert video.moderation_status == MOD_PENDING_REVIEW


def test_invalid_decision_is_rejected(db, video):
    _as_user(ADMIN_ID)
    resp = client.post(
        f"/api/v1/moderation/videos/{video.id}/review", json={"decision": "maybe"},
    )
    assert resp.status_code == 400


def test_reviewing_unknown_video_404s():
    _as_user(ADMIN_ID)
    resp = client.post(
        "/api/v1/moderation/videos/does-not-exist/review", json={"decision": "approve"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Feed filtering
# ---------------------------------------------------------------------------

def test_pending_review_video_excluded_from_feed(db, video):
    video.moderation_status = MOD_PENDING_REVIEW
    db.commit()

    resp = client.get("/api/v1/videos/feed", params={"place_id": video.place_id})
    ids = [v["id"] for v in resp.json()["videos"]]
    assert video.id not in ids


def test_approved_video_appears_in_feed(video):
    resp = client.get("/api/v1/videos/feed", params={"place_id": video.place_id})
    ids = [v["id"] for v in resp.json()["videos"]]
    assert video.id in ids
