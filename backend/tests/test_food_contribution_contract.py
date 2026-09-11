from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.routes.contributions import ContributionCreate
from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.models.activity_event import ActivityEvent, EVENT_POSTED_FOOD
from app.db.models.food_contribution import FoodContribution, STATUS_DELETED
from app.db.models.place_image import PlaceImage
from app.db.models.visit_evidence import VisitEvidence
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)
PLACE_ID = "00000000-0000-0000-0000-000000000002"


def _payload(**overrides):
    data = {
        "client_id": f"draft-{uuid.uuid4()}",
        "place_id": PLACE_ID,
        "intent": "private_log",
        "reaction": "good",
        "caption": "Dinner",
        "visibility": "private",
    }
    data.update(overrides)
    return data


def _as_user(user_id: str) -> None:
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


def _cleanup_user(db, user_id: str) -> None:
    db.query(ActivityEvent).filter(ActivityEvent.user_id == user_id).delete(synchronize_session=False)
    db.query(VisitEvidence).filter(VisitEvidence.user_id == user_id).delete(synchronize_session=False)
    db.query(FoodContribution).filter(FoodContribution.user_id == user_id).delete(synchronize_session=False)
    db.query(PlaceImage).filter(PlaceImage.uploaded_by == user_id).delete(synchronize_session=False)
    db.commit()


def test_private_log_can_commit_without_media() -> None:
    parsed = ContributionCreate(**_payload())
    assert parsed.intent == "private_log"
    assert parsed.image_id is None
    assert parsed.video_id is None


def test_private_log_cannot_escape_private_visibility() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(visibility="public"))


def test_social_post_requires_media_and_explicit_social_audience() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(intent="social_post", visibility="public"))
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(intent="social_post", visibility="private", image_id="image-1"))

    parsed = ContributionCreate(
        **_payload(intent="social_post", visibility="connections", image_id="image-1")
    )
    assert parsed.visibility == "connections"


def test_contribution_rejects_two_media_assets() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(
            **_payload(intent="social_post", visibility="public", image_id="image-1", video_id="video-1")
        )


def test_occurred_at_requires_timezone_and_cannot_be_future() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(occurred_at=datetime.now()))
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(occurred_at=datetime.now(timezone.utc) + timedelta(minutes=1)))

    occurred = datetime.now(timezone.utc) - timedelta(days=2)
    parsed = ContributionCreate(**_payload(occurred_at=occurred))
    assert parsed.occurred_at == occurred


def test_reaction_vocabulary_is_closed() -> None:
    with pytest.raises(ValidationError):
        ContributionCreate(**_payload(reaction="five_stars"))


def test_endpoint_idempotent_replay_returns_same_row_and_timezone_safe(db) -> None:
    user_id = f"contrib-{uuid.uuid4()}"
    _as_user(user_id)
    occurred = datetime.now(timezone(timedelta(hours=-7))) - timedelta(days=1)
    payload = _payload(client_id=f"idem-{uuid.uuid4()}", occurred_at=occurred, caption="  Dinner  ")
    try:
        first = client.post("/api/v1/contributions", json={**payload, "occurred_at": occurred.isoformat()})
        second = client.post("/api/v1/contributions", json={**payload, "occurred_at": occurred.isoformat()})
        assert first.status_code == 201, first.text
        assert second.status_code == 201, second.text
        assert second.json()["id"] == first.json()["id"]
        assert second.json()["caption"] == "Dinner"
        assert db.query(FoodContribution).filter(FoodContribution.user_id == user_id).count() == 1
    finally:
        _cleanup_user(db, user_id)


def test_endpoint_idempotent_payload_drift_returns_409(db) -> None:
    user_id = f"contrib-{uuid.uuid4()}"
    _as_user(user_id)
    client_id = f"drift-{uuid.uuid4()}"
    try:
        first = client.post("/api/v1/contributions", json=_payload(client_id=client_id, reaction="good"))
        assert first.status_code == 201, first.text
        replay = client.post("/api/v1/contributions", json=_payload(client_id=client_id, reaction="loved"))
        assert replay.status_code == 409
    finally:
        _cleanup_user(db, user_id)


def test_endpoint_deleted_client_id_cannot_be_replayed(db) -> None:
    user_id = f"contrib-{uuid.uuid4()}"
    _as_user(user_id)
    payload = _payload(client_id=f"deleted-{uuid.uuid4()}")
    try:
        created = client.post("/api/v1/contributions", json=payload)
        assert created.status_code == 201, created.text
        deleted = client.delete(f"/api/v1/contributions/{created.json()['id']}")
        assert deleted.status_code == 204, deleted.text
        replay = client.post("/api/v1/contributions", json=payload)
        assert replay.status_code == 409
        db.expire_all()
        row = db.get(FoodContribution, created.json()["id"])
        assert row is not None and row.status == STATUS_DELETED
    finally:
        _cleanup_user(db, user_id)


def test_endpoint_missing_place_returns_404(db) -> None:
    user_id = f"contrib-{uuid.uuid4()}"
    _as_user(user_id)
    try:
        response = client.post(
            "/api/v1/contributions",
            json=_payload(place_id="ffffffff-ffff-ffff-ffff-ffffffffffff"),
        )
        assert response.status_code == 404
    finally:
        _cleanup_user(db, user_id)


def test_endpoint_rejects_media_owned_by_another_user(db) -> None:
    owner = f"owner-{uuid.uuid4()}"
    attacker = f"other-{uuid.uuid4()}"
    image = PlaceImage(
        id=str(uuid.uuid4()),
        place_id=PLACE_ID,
        url="https://example.test/owned.jpg",
        uploaded_by=owner,
        content_type="food",
    )
    db.add(image)
    db.commit()
    _as_user(attacker)
    try:
        response = client.post(
            "/api/v1/contributions",
            json=_payload(
                intent="social_post",
                visibility="public",
                image_id=image.id,
            ),
        )
        assert response.status_code == 404
    finally:
        _cleanup_user(db, attacker)
        _cleanup_user(db, owner)


def test_get_and_delete_are_owner_scoped(db) -> None:
    owner = f"contrib-{uuid.uuid4()}"
    other = f"contrib-{uuid.uuid4()}"
    _as_user(owner)
    try:
        created = client.post("/api/v1/contributions", json=_payload())
        assert created.status_code == 201, created.text
        contribution_id = created.json()["id"]

        _as_user(other)
        assert client.get(f"/api/v1/contributions/{contribution_id}").status_code == 404
        assert client.delete(f"/api/v1/contributions/{contribution_id}").status_code == 404

        _as_user(owner)
        assert client.get(f"/api/v1/contributions/{contribution_id}").status_code == 200
    finally:
        _cleanup_user(db, owner)
        _cleanup_user(db, other)


def test_authenticated_user_is_the_contribution_owner(db) -> None:
    user_id = f"token-owner-{uuid.uuid4()}"
    _as_user(user_id)
    try:
        body = _payload()
        body["user_id"] = "forged-user"
        response = client.post("/api/v1/contributions", json=body)
        assert response.status_code == 201, response.text
        db.expire_all()
        row = db.get(FoodContribution, response.json()["id"])
        assert row is not None
        assert row.user_id == user_id
    finally:
        _cleanup_user(db, user_id)


def test_social_contribution_creates_activity_pointer_and_delete_retracts_it(db) -> None:
    user_id = f"social-contrib-{uuid.uuid4()}"
    _as_user(user_id)
    image = PlaceImage(
        id=str(uuid.uuid4()),
        place_id=PLACE_ID,
        url="https://example.test/social.jpg",
        uploaded_by=user_id,
        content_type="food",
    )
    db.add(image)
    db.commit()
    try:
        created = client.post(
            "/api/v1/contributions",
            json=_payload(
                intent="social_post",
                visibility="connections",
                reaction="loved",
                image_id=image.id,
            ),
        )
        assert created.status_code == 201, created.text
        contribution_id = created.json()["id"]
        db.expire_all()
        event = (
            db.query(ActivityEvent)
            .filter(
                ActivityEvent.user_id == user_id,
                ActivityEvent.event_type == EVENT_POSTED_FOOD,
            )
            .one()
        )
        assert event.place_id == PLACE_ID
        assert event.payload == {
            "contribution_id": contribution_id,
            "visibility": "connections",
            "reaction": "loved",
        }

        deleted = client.delete(f"/api/v1/contributions/{contribution_id}")
        assert deleted.status_code == 204
        db.expire_all()
        assert (
            db.query(ActivityEvent)
            .filter(
                ActivityEvent.user_id == user_id,
                ActivityEvent.event_type == EVENT_POSTED_FOOD,
            )
            .count()
            == 0
        )
    finally:
        _cleanup_user(db, user_id)
