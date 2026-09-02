"""
Coverage for app/api/v1/routes/moderation.py's place-report endpoints --
the place-level counterpart to ImageReport/VideoReport (see
test_moderation_routes.py). Until this existed there was no way for a
user to flag wrong hours, a closure, a duplicate listing, or wrong menu
info from inside the app at all.

Deliberately no auto-hide coverage here: unlike images/videos, a place
is never auto-deactivated on report volume -- every test that matters
here is about recording, deduplicating, and queueing for a human, not
about an automatic content-visibility consequence.
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
from app.db.models.place_report import PlaceReport

client = TestClient(app)

ADMIN_ID = "place-report-admin-fixture"


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
def place(db):
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"placereport-{suffix}", name=f"PlaceReport City {suffix}")
    db.add(city)
    db.flush()
    p = Place(name=f"PlaceReport Place {suffix}", city_id=city.id)
    db.add(p)
    db.commit()

    yield p

    db.query(PlaceReport).filter(PlaceReport.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def test_reporting_a_place_records_it(db, place):
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/places/{place.id}/report",
        json={"reason": "wrong_hours"},
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "reported"
    assert db.query(PlaceReport).filter(PlaceReport.place_id == place.id).count() == 1


def test_same_user_reporting_twice_is_idempotent(db, place):
    _as_user("reporter-a")
    first = client.post(
        f"/api/v1/moderation/places/{place.id}/report", json={"reason": "closed"},
    )
    second = client.post(
        f"/api/v1/moderation/places/{place.id}/report", json={"reason": "duplicate"},
    )

    assert first.status_code == 201
    assert second.json()["status"] == "already_reported"
    assert db.query(PlaceReport).filter(PlaceReport.place_id == place.id).count() == 1


def test_a_report_never_touches_the_place_itself(db, place):
    """No auto-hide/deactivate path exists for places -- unlike an image,
    a whole restaurant is never taken off the catalog on report volume
    alone."""
    for i in range(5):
        _as_user(f"reporter-{i}")
        client.post(
            f"/api/v1/moderation/places/{place.id}/report",
            json={"reason": "wrong_hours"},
        )

    db.refresh(place)
    assert place.is_active is True


def test_invalid_reason_is_rejected(place):
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/places/{place.id}/report", json={"reason": "i_dislike_it"},
    )
    assert resp.status_code == 400


def test_reporting_unknown_place_404s():
    _as_user("reporter-a")
    resp = client.post(
        "/api/v1/moderation/places/does-not-exist/report", json={"reason": "closed"},
    )
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Review queue -- admin gated
# ---------------------------------------------------------------------------

def test_queue_is_invisible_to_non_admins(place):
    _as_user("not-an-admin")
    resp = client.get("/api/v1/moderation/places/queue")
    assert resp.status_code == 404


def test_queue_fails_closed_when_no_admins_configured(monkeypatch, place):
    monkeypatch.delenv("ADMIN_USER_IDS", raising=False)
    _as_user(ADMIN_ID)
    resp = client.get("/api/v1/moderation/places/queue")
    assert resp.status_code == 404


def test_queue_lists_places_with_unresolved_reports(db, place):
    _as_user("reporter-a")
    client.post(
        f"/api/v1/moderation/places/{place.id}/report", json={"reason": "wrong_hours"},
    )
    _as_user("reporter-b")
    client.post(
        f"/api/v1/moderation/places/{place.id}/report", json={"reason": "closed"},
    )

    _as_user(ADMIN_ID)
    resp = client.get("/api/v1/moderation/places/queue")
    assert resp.status_code == 200
    queue = resp.json()["queue"]
    entry = next(e for e in queue if e["place_id"] == place.id)
    assert entry["place_name"] == place.name
    assert entry["report_count"] == 2
    assert sorted(entry["reasons"]) == ["closed", "wrong_hours"]


def test_queue_excludes_resolved_reports(db, place):
    _as_user("reporter-a")
    resp = client.post(
        f"/api/v1/moderation/places/{place.id}/report", json={"reason": "wrong_hours"},
    )
    report_id = db.query(PlaceReport).filter(PlaceReport.place_id == place.id).one().id

    _as_user(ADMIN_ID)
    resolve = client.post(f"/api/v1/moderation/places/reports/{report_id}/resolve")
    assert resolve.status_code == 200
    assert resolve.json()["status"] == "resolved"

    queue = client.get("/api/v1/moderation/places/queue").json()["queue"]
    assert not any(e["place_id"] == place.id for e in queue)


def test_resolve_requires_admin(db, place):
    _as_user("reporter-a")
    client.post(
        f"/api/v1/moderation/places/{place.id}/report", json={"reason": "wrong_hours"},
    )
    report_id = db.query(PlaceReport).filter(PlaceReport.place_id == place.id).one().id

    _as_user("not-an-admin")
    resp = client.post(f"/api/v1/moderation/places/reports/{report_id}/resolve")
    assert resp.status_code == 404


def test_resolving_unknown_report_404s():
    _as_user(ADMIN_ID)
    resp = client.post("/api/v1/moderation/places/reports/does-not-exist/resolve")
    assert resp.status_code == 404
