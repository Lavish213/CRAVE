"""
Coverage for app/api/v1/routes/menu_submissions.py and
app/services/menu/user_submission_service.py — the restaurant/user menu
self-submission path.

A submission is staged in menu_submissions and never trusted directly.
Only on approval does app.services.menu.user_submission_service write
PlaceClaim rows and run the existing materialize_menu_truth ->
MenuPublisher pipeline, so these tests check both the queue mechanics
(mirroring test_moderation_routes.py's admin-gating pattern) and that an
approval actually produces servable MenuItem rows.
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
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.db.models.menu_item import MenuItem
from app.db.models.menu_submission import (
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    MenuSubmission,
)

client = TestClient(app)

ADMIN_ID = "menu-submission-admin-fixture"


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
    city = City(slug=f"menusub-{suffix}", name=f"MenuSub City {suffix}")
    db.add(city)
    db.flush()
    p = Place(name=f"MenuSub Place {suffix}", city_id=city.id, is_active=True)
    db.add(p)
    db.commit()

    yield p

    db.query(MenuItem).filter(MenuItem.place_id == p.id).delete()
    db.query(PlaceTruth).filter(PlaceTruth.place_id == p.id).delete()
    db.query(PlaceClaim).filter(PlaceClaim.place_id == p.id).delete()
    db.query(MenuSubmission).filter(MenuSubmission.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


_TWO_ITEMS = [
    {"name": "Cheeseburger", "category": "Entrees", "price_cents": 1299, "description": "with fries"},
    {"name": "Caesar Salad", "category": "Starters", "price_cents": 899},
]


# ---------------------------------------------------------------------------
# Submitting
# ---------------------------------------------------------------------------

def test_submitting_a_menu_creates_a_pending_row(db, place):
    _as_user("submitter-a")
    resp = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": _TWO_ITEMS},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == STATUS_PENDING
    assert body["item_count"] == 2

    row = db.query(MenuSubmission).filter(MenuSubmission.id == body["id"]).one()
    assert row.place_id == place.id
    assert row.submitted_by == "submitter-a"
    assert len(row.items) == 2


def test_submitting_to_unknown_place_404s():
    _as_user("submitter-a")
    resp = client.post(
        "/api/v1/places/does-not-exist/menu/submit", json={"items": _TWO_ITEMS},
    )
    assert resp.status_code == 404


def test_submitting_empty_items_is_rejected(place):
    _as_user("submitter-a")
    resp = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": []},
    )
    assert resp.status_code == 422


def test_submitted_by_is_server_set_from_auth_not_client_input(db, place):
    """submitted_by must come from the verified token, never client JSON —
    same IDOR class user_auth.py's docstring warns about elsewhere."""
    _as_user("real-user")
    resp = client.post(
        f"/api/v1/places/{place.id}/menu/submit",
        json={"items": _TWO_ITEMS, "submitted_by": "someone-else"},
    )
    assert resp.status_code == 201
    row = db.query(MenuSubmission).filter(MenuSubmission.id == resp.json()["id"]).one()
    assert row.submitted_by == "real-user"


# ---------------------------------------------------------------------------
# Review queue — admin gated
# ---------------------------------------------------------------------------

def test_queue_is_invisible_to_non_admins(place):
    _as_user("ordinary-user")
    assert client.get("/api/v1/moderation/menu-submissions").status_code == 404


def test_queue_lists_pending_submissions(db, place):
    _as_user("submitter-a")
    resp = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": _TWO_ITEMS},
    )
    submission_id = resp.json()["id"]

    _as_user(ADMIN_ID)
    queue = client.get("/api/v1/moderation/menu-submissions").json()["queue"]
    assert any(row["id"] == submission_id for row in queue)


def test_get_submission_detail_requires_admin(db, place):
    _as_user("submitter-a")
    submission_id = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": _TWO_ITEMS},
    ).json()["id"]

    _as_user("ordinary-user")
    assert client.get(f"/api/v1/moderation/menu-submissions/{submission_id}").status_code == 404

    _as_user(ADMIN_ID)
    resp = client.get(f"/api/v1/moderation/menu-submissions/{submission_id}")
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()["items"]}
    assert names == {"Cheeseburger", "Caesar Salad"}


# ---------------------------------------------------------------------------
# Reviewing — rejection
# ---------------------------------------------------------------------------

def test_rejecting_a_submission_records_reason_and_writes_no_claims(db, place):
    _as_user("submitter-a")
    submission_id = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": _TWO_ITEMS},
    ).json()["id"]

    _as_user(ADMIN_ID)
    resp = client.post(
        f"/api/v1/moderation/menu-submissions/{submission_id}/review",
        json={"decision": "reject", "rejection_reason": "duplicate of an existing menu"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == STATUS_REJECTED

    row = db.query(MenuSubmission).filter(MenuSubmission.id == submission_id).one()
    assert row.status == STATUS_REJECTED
    assert row.rejection_reason == "duplicate of an existing menu"
    assert row.reviewed_by == ADMIN_ID
    assert row.reviewed_at is not None
    assert db.query(PlaceClaim).filter(PlaceClaim.place_id == place.id).count() == 0


def test_review_requires_admin(db, place):
    _as_user("submitter-a")
    submission_id = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": _TWO_ITEMS},
    ).json()["id"]

    _as_user("ordinary-user")
    resp = client.post(
        f"/api/v1/moderation/menu-submissions/{submission_id}/review",
        json={"decision": "approve"},
    )
    assert resp.status_code == 404

    row = db.query(MenuSubmission).filter(MenuSubmission.id == submission_id).one()
    assert row.status == STATUS_PENDING


def test_reviewing_an_already_reviewed_submission_conflicts(db, place):
    _as_user("submitter-a")
    submission_id = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": _TWO_ITEMS},
    ).json()["id"]

    _as_user(ADMIN_ID)
    client.post(
        f"/api/v1/moderation/menu-submissions/{submission_id}/review",
        json={"decision": "reject"},
    )
    resp = client.post(
        f"/api/v1/moderation/menu-submissions/{submission_id}/review",
        json={"decision": "approve"},
    )
    assert resp.status_code == 409


# ---------------------------------------------------------------------------
# Reviewing — approval writes claims and publishes a real menu
# ---------------------------------------------------------------------------

def test_approving_a_submission_publishes_it_to_menu_items(db, place):
    _as_user("submitter-a")
    submission_id = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": _TWO_ITEMS},
    ).json()["id"]

    _as_user(ADMIN_ID)
    resp = client.post(
        f"/api/v1/moderation/menu-submissions/{submission_id}/review",
        json={"decision": "approve"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == STATUS_APPROVED
    assert resp.json()["published_items"] == 2

    claims = (
        db.query(PlaceClaim)
        .filter(PlaceClaim.place_id == place.id, PlaceClaim.field == "menu_item")
        .all()
    )
    assert len(claims) == 2
    assert all(c.source == "user_submission" for c in claims)
    assert all(c.is_verified_source is True for c in claims)
    assert all(c.is_user_submitted is True for c in claims)

    published = db.query(MenuItem).filter(MenuItem.place_id == place.id).all()
    published_names = {m.name for m in published}
    assert published_names == {"Cheeseburger", "Caesar Salad"}

    db.refresh(place)
    assert place.has_menu is True


def test_approval_failure_leaves_submission_pending_and_retryable(db, place, monkeypatch):
    """
    Confirmed bug: the route used to commit status=APPROVED before calling
    apply_approved_submission, so a failure inside it (materialize_menu_truth
    is a nontrivial scoring pipeline -- a plausible place for a transient
    bug) left the submission permanently stuck "approved" with
    published_items=0, and the 409-on-non-PENDING guard meant there was no
    way to even retry via this same endpoint.
    """
    import app.api.v1.routes.menu_submissions as menu_submissions_route

    _as_user("submitter-b")
    submission_id = client.post(
        f"/api/v1/places/{place.id}/menu/submit", json={"items": _TWO_ITEMS},
    ).json()["id"]

    real_apply = menu_submissions_route.apply_approved_submission

    def _boom(*, db, submission):
        raise RuntimeError("materialize_menu_truth blew up")

    monkeypatch.setattr(menu_submissions_route, "apply_approved_submission", _boom)

    _as_user(ADMIN_ID)
    resp = client.post(
        f"/api/v1/moderation/menu-submissions/{submission_id}/review",
        json={"decision": "approve"},
    )
    assert resp.status_code == 500

    submission = db.query(MenuSubmission).filter(MenuSubmission.id == submission_id).one()
    assert submission.status == STATUS_PENDING
    assert submission.reviewed_at is None
    assert submission.reviewed_by is None

    # Retryable now that the failure is fixed -- a second approve attempt
    # against the still-PENDING submission succeeds. Restoring just this
    # one attribute (not monkeypatch.undo(), which would also revert the
    # autouse _overrides fixture's ADMIN_USER_IDS patch on this same
    # per-test monkeypatch instance).
    monkeypatch.setattr(menu_submissions_route, "apply_approved_submission", real_apply)
    resp = client.post(
        f"/api/v1/moderation/menu-submissions/{submission_id}/review",
        json={"decision": "approve"},
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == STATUS_APPROVED


def test_approving_a_second_submission_for_the_same_item_updates_the_claim_not_duplicates(db, place):
    """Same place, same item (same fingerprint) submitted twice — the
    second approval must update the existing claim in place, not create a
    second competing claim under the same source. Both submissions include
    a second, unchanging item so the aggregate item_count still clears
    materialize_menu_truth's MIN_TRUTH_ITEMS floor of 2."""
    _as_user("submitter-a")
    first_id = client.post(
        f"/api/v1/places/{place.id}/menu/submit",
        json={"items": [
            {"name": "Cheeseburger", "category": "Entrees", "price_cents": 1299},
            {"name": "Fries", "category": "Sides", "price_cents": 399},
        ]},
    ).json()["id"]

    _as_user(ADMIN_ID)
    client.post(
        f"/api/v1/moderation/menu-submissions/{first_id}/review",
        json={"decision": "approve"},
    )

    _as_user("submitter-b")
    second_id = client.post(
        f"/api/v1/places/{place.id}/menu/submit",
        json={"items": [
            {"name": "Cheeseburger", "category": "Entrees", "price_cents": 1399},
            {"name": "Fries", "category": "Sides", "price_cents": 399},
        ]},
    ).json()["id"]

    _as_user(ADMIN_ID)
    client.post(
        f"/api/v1/moderation/menu-submissions/{second_id}/review",
        json={"decision": "approve"},
    )

    claims = (
        db.query(PlaceClaim)
        .filter(
            PlaceClaim.place_id == place.id,
            PlaceClaim.field == "menu_item",
            PlaceClaim.source == "user_submission",
        )
        .all()
    )
    assert len(claims) == 2
    burger_claim = next(c for c in claims if c.value_json["name"] == "Cheeseburger")
    assert burger_claim.value_json["price_cents"] == 1399

    published = db.query(MenuItem).filter(MenuItem.place_id == place.id).all()
    assert len(published) == 2
    burger = next(m for m in published if m.name == "Cheeseburger")
    assert burger.price_cents == 1399
