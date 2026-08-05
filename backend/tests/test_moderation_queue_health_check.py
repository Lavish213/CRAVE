"""
Coverage for app.scheduler._job_moderation_queue_health_check.

require_admin (app/api/v1/routes/moderation.py) deliberately fails closed
if ADMIN_USER_IDS is unset — correct for the route, but it means an
accidentally-unset env var previously produced no signal anywhere: the
review queue just silently piles up forever with nobody able to drain it.
This job makes that condition loud (logger.error, which Sentry's default
LoggingIntegration turns into a real event) instead of silent.
"""
from __future__ import annotations

import logging
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.models.job_run import JobRun
from app.services.images.upload_moderation import MOD_PENDING_REVIEW, MOD_APPROVED
from app.scheduler import _job_moderation_queue_health_check


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
    city = City(slug=f"modhealth-test-{suffix}", name=f"Mod Health Test City {suffix}")
    db.add(city)
    db.flush()

    p = Place(name=f"Mod Health Test Place {suffix}", city_id=city.id, is_active=True)
    db.add(p)
    db.commit()

    yield p

    db.query(PlaceImage).filter(PlaceImage.place_id == p.id).delete()
    db.query(JobRun).filter(JobRun.job_name == "moderation_queue_health_check").delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def _make_image(db, place, moderation_status):
    img = PlaceImage(
        place_id=place.id,
        url="https://example.com/x.jpg",
        moderation_status=moderation_status,
    )
    db.add(img)
    db.commit()
    return img


def test_no_pending_images_logs_nothing_alarming(db, place, monkeypatch, caplog):
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    _make_image(db, place, MOD_APPROVED)

    with caplog.at_level(logging.ERROR):
        _job_moderation_queue_health_check()

    assert not any("moderation_queue_undrainable" in r.message for r in caplog.records)


def test_pending_images_with_admins_configured_is_not_an_error(db, place, monkeypatch, caplog):
    monkeypatch.setenv("ADMIN_USER_IDS", "some-admin-user-id")
    _make_image(db, place, MOD_PENDING_REVIEW)

    with caplog.at_level(logging.ERROR):
        _job_moderation_queue_health_check()

    assert not any("moderation_queue_undrainable" in r.message for r in caplog.records)


def test_pending_images_with_no_admins_configured_logs_error(db, place, monkeypatch, caplog):
    # The exact deadlock: pending review items exist, but nobody can reach
    # the review endpoint to clear them (require_admin 404s everyone).
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    _make_image(db, place, MOD_PENDING_REVIEW)

    with caplog.at_level(logging.ERROR):
        _job_moderation_queue_health_check()

    assert any(
        r.levelno == logging.ERROR and "moderation_queue_undrainable" in r.message
        for r in caplog.records
    )


def test_pending_images_with_blank_admin_ids_still_counts_as_unconfigured(db, place, monkeypatch, caplog):
    # "" and whitespace-only should behave identically to unset — _admin_ids()
    # already strips/filters empty parts, this just confirms the health
    # check relies on that same parsing rather than a naive truthiness check.
    monkeypatch.setenv("ADMIN_USER_IDS", "  , ,")
    _make_image(db, place, MOD_PENDING_REVIEW)

    with caplog.at_level(logging.ERROR):
        _job_moderation_queue_health_check()

    assert any(
        r.levelno == logging.ERROR and "moderation_queue_undrainable" in r.message
        for r in caplog.records
    )
