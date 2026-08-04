"""
Coverage for app/api/v1/routes/moderation.py — user reports plus the
review queue.

Until this existed there was no takedown path of any kind: is_approved was
hardcoded True at upload and nothing anywhere ever set it False, so
removing a photo required direct database access.
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
from app.db.models.image_report import AUTO_HIDE_REPORT_COUNT, ImageReport
from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_GALLERY_ONLY,
    VISIBILITY_HIDDEN,
    VISIBILITY_SHOWCASE,
)
from app.services.images.upload_moderation import (
    MOD_APPROVED,
    MOD_PENDING_REVIEW,
    MOD_REJECTED,
)

client = TestClient(app)

ADMIN_ID = "moderation-admin-fixture"


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    # Shared per-process rate-limit bucket across TestClient files — see
    # the note in test_social_routes_integration.py.
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
def image(db):
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"modroute-{suffix}", name=f"ModRoute City {suffix}")
    db.add(city)
    db.flush()
    place = Place(name=f"ModRoute Place {suffix}", city_id=city.id)
    db.add(place)
    db.flush()
    img = PlaceImage(
        place_id=place.id,
        url="https://example.com/photo.jpg",
        moderation_status=MOD_APPROVED,
        is_approved=True,
        is_primary=True,
        visibility_status=VISIBILITY_SHOWCASE,
        uploaded_by="uploader-1",
    )
    db.add(img)
    db.commit()

    yield img

    db.query(ImageReport).filter(ImageReport.image_id == img.id).delete()
    db.query(PlaceImage).filter(PlaceImage.place_id == place.id).delete()
    db.query(Place).filter(Place.id == place.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def test_reporting_an_image_records_it(db, image):
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/images/{image.id}/report",
        json={"reason": "inappropriate"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "reported"

    assert db.query(ImageReport).filter(ImageReport.image_id == image.id).count() == 1


def test_a_single_report_does_not_hide_the_image(db, image):
    """One report is an opinion and can be malicious — a rival business, a
    grudge. It must not be enough to pull live content on its own."""
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/images/{image.id}/report", json={"reason": "spam"},
    )
    assert resp.json()["withheld"] is False

    db.refresh(image)
    assert image.moderation_status == MOD_APPROVED
    assert image.visibility_status == VISIBILITY_SHOWCASE


def test_same_user_reporting_twice_is_idempotent(db, image):
    _as_user("reporter-a")
    first = client.post(
        f"/api/v1/moderation/images/{image.id}/report", json={"reason": "spam"},
    )
    second = client.post(
        f"/api/v1/moderation/images/{image.id}/report", json={"reason": "spam"},
    )

    assert first.status_code == 201
    assert second.json()["status"] == "already_reported"
    # Otherwise one person could trip the auto-hide threshold alone.
    assert db.query(ImageReport).filter(ImageReport.image_id == image.id).count() == 1


def test_enough_distinct_reports_withholds_the_image(db, image):
    for i in range(AUTO_HIDE_REPORT_COUNT):
        _as_user(f"reporter-{i}")
        resp = client.post(
            f"/api/v1/moderation/images/{image.id}/report",
            json={"reason": "inappropriate"},
        )

    assert resp.json()["withheld"] is True

    db.refresh(image)
    assert image.moderation_status == MOD_PENDING_REVIEW
    assert image.is_approved is False
    assert image.is_primary is False
    # Hidden is what every read path (gallery, feed card, map pin) filters on.
    assert image.visibility_status == VISIBILITY_HIDDEN


def test_auto_hide_holds_for_review_rather_than_deleting(db, image):
    """A coordinated bad-faith pile-on has to stay recoverable."""
    for i in range(AUTO_HIDE_REPORT_COUNT):
        _as_user(f"reporter-{i}")
        client.post(
            f"/api/v1/moderation/images/{image.id}/report", json={"reason": "spam"},
        )

    db.refresh(image)
    assert image.moderation_status == MOD_PENDING_REVIEW
    assert image.moderation_status != MOD_REJECTED
    assert db.query(PlaceImage).filter(PlaceImage.id == image.id).count() == 1


def test_invalid_reason_is_rejected(image):
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/images/{image.id}/report", json={"reason": "i_dislike_it"},
    )
    assert resp.status_code == 400


def test_reporting_unknown_image_404s():
    _as_user("reporter-a")
    resp = client.post(
        "/api/v1/moderation/images/does-not-exist/report", json={"reason": "spam"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Review queue — admin gated
# ---------------------------------------------------------------------------

def test_queue_is_invisible_to_non_admins(image):
    _as_user("ordinary-user")
    # 404 not 403 — don't advertise that the queue exists.
    assert client.get("/api/v1/moderation/queue").status_code == 404


def test_queue_fails_closed_when_no_admins_configured(monkeypatch, image):
    monkeypatch.setenv("ADMIN_USER_IDS", "")
    _as_user(ADMIN_ID)
    assert client.get("/api/v1/moderation/queue").status_code == 404


def test_queue_lists_pending_images_with_their_signals(db, image):
    image.moderation_status = MOD_PENDING_REVIEW
    image.moderation_reason = "safety_review_racy"
    image.blur_score = 412.0
    image.quality_score = 0.8
    db.commit()

    _as_user(ADMIN_ID)
    resp = client.get("/api/v1/moderation/queue")

    assert resp.status_code == 200
    row = next(r for r in resp.json()["queue"] if r["image_id"] == image.id)
    assert row["moderation_reason"] == "safety_review_racy"
    assert row["blur_score"] == 412.0
    assert row["report_count"] == 0


def test_queue_excludes_already_approved_images(db, image):
    _as_user(ADMIN_ID)
    ids = [r["image_id"] for r in client.get("/api/v1/moderation/queue").json()["queue"]]
    assert image.id not in ids


def test_queue_reports_the_report_count(db, image):
    for i in range(2):
        _as_user(f"reporter-{i}")
        client.post(
            f"/api/v1/moderation/images/{image.id}/report", json={"reason": "spam"},
        )
    image.moderation_status = MOD_PENDING_REVIEW
    db.commit()

    _as_user(ADMIN_ID)
    row = next(
        r for r in client.get("/api/v1/moderation/queue").json()["queue"]
        if r["image_id"] == image.id
    )
    assert row["report_count"] == 2


# ---------------------------------------------------------------------------
# Resolving a review
# ---------------------------------------------------------------------------

def test_approving_restores_visibility_but_not_primary(db, image):
    image.moderation_status = MOD_PENDING_REVIEW
    image.is_approved = False
    image.is_primary = False
    image.visibility_status = VISIBILITY_HIDDEN
    db.commit()

    _as_user(ADMIN_ID)
    resp = client.post(
        f"/api/v1/moderation/images/{image.id}/review", json={"decision": "approve"},
    )
    assert resp.status_code == 200

    db.refresh(image)
    assert image.moderation_status == MOD_APPROVED
    assert image.is_approved is True
    # "Allowed to be seen" is not "should be the face of this place" —
    # primary election stays with the invariant service, which ranks on
    # quality rather than on who happened to be reviewed last.
    assert image.visibility_status == VISIBILITY_GALLERY_ONLY
    assert image.reviewed_by == ADMIN_ID
    assert image.reviewed_at is not None


def test_rejecting_hides_the_image_permanently(db, image):
    image.moderation_status = MOD_PENDING_REVIEW
    db.commit()

    _as_user(ADMIN_ID)
    client.post(
        f"/api/v1/moderation/images/{image.id}/review", json={"decision": "reject"},
    )

    db.refresh(image)
    assert image.moderation_status == MOD_REJECTED
    assert image.is_approved is False
    assert image.is_primary is False
    assert image.visibility_status == VISIBILITY_HIDDEN


def test_review_requires_admin(db, image):
    image.moderation_status = MOD_PENDING_REVIEW
    db.commit()

    _as_user("ordinary-user")
    resp = client.post(
        f"/api/v1/moderation/images/{image.id}/review", json={"decision": "approve"},
    )
    assert resp.status_code == 404

    db.refresh(image)
    assert image.moderation_status == MOD_PENDING_REVIEW


def test_invalid_decision_is_rejected(db, image):
    _as_user(ADMIN_ID)
    resp = client.post(
        f"/api/v1/moderation/images/{image.id}/review", json={"decision": "maybe"},
    )
    assert resp.status_code == 400
