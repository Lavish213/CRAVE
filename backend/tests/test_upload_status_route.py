"""
Coverage for GET /upload/status/{image_id} -- specifically that it
exposes moderation_status/moderation_reason alongside the processing
status.

Before this, the route only returned `status` (the processing-pipeline
lifecycle: pending/processing/ready/failed), which reaches "ready" as
soon as a photo finishes processing regardless of the separate
moderation decision (see PlaceImage.moderation_status's own docstring).
A caller polling this endpoint had no way to tell a photo that's
actually live from one silently held pending human review -- both
report status="ready".
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
from app.db.models.place_image import PlaceImage
from app.services.images.upload_moderation import MOD_APPROVED, MOD_PENDING_REVIEW

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
    city = City(slug=f"upload-status-test-{suffix}", name=f"Upload Status Test City {suffix}")
    db.add(city)
    db.commit()
    p = Place(name=f"Place {suffix}", city_id=city.id, is_active=True, rank_score=1.0)
    db.add(p)
    db.commit()
    yield p
    db.query(PlaceImage).filter(PlaceImage.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def _make_image(db, place, *, status: str, moderation_status: str, moderation_reason=None) -> PlaceImage:
    img = PlaceImage(
        place_id=place.id,
        uploaded_by="user-a",
        status=status,
        moderation_status=moderation_status,
        moderation_reason=moderation_reason,
    )
    db.add(img)
    db.commit()
    return img


def test_ready_and_approved_reports_both_fields(db, place):
    _as_user("user-a")
    img = _make_image(db, place, status="ready", moderation_status=MOD_APPROVED)

    resp = client.get(f"/api/v1/upload/status/{img.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["moderation_status"] == MOD_APPROVED


def test_ready_but_pending_review_is_distinguishable_from_approved(db, place):
    """The exact bug this endpoint used to hide: a photo can finish
    processing (status=ready) while still being held for human review."""
    _as_user("user-a")
    img = _make_image(
        db, place, status="ready", moderation_status=MOD_PENDING_REVIEW,
        moderation_reason="untrusted_contributor",
    )

    resp = client.get(f"/api/v1/upload/status/{img.id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ready"
    assert body["moderation_status"] == MOD_PENDING_REVIEW
    assert body["moderation_reason"] == "untrusted_contributor"


def test_missing_image_returns_404(db):
    _as_user("user-a")
    resp = client.get(f"/api/v1/upload/status/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_another_users_upload_is_not_readable(db, place):
    """IDOR guard: this route requires auth but the image_id itself is an
    unguessable-in-theory but otherwise unauthorized-access-checked path
    param -- without an ownership check, any authenticated caller could
    poll any other user's upload and read moderation_reason/error, which
    can contain review-queue detail (e.g. why a photo was flagged) that
    isn't meant for anyone but the uploader."""
    img = _make_image(
        db, place, status="ready", moderation_status=MOD_PENDING_REVIEW,
        moderation_reason="untrusted_contributor",
    )

    _as_user("someone-else")
    resp = client.get(f"/api/v1/upload/status/{img.id}")

    assert resp.status_code == 403
