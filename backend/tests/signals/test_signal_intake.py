# tests/signals/test_signal_intake.py
"""
Tests for the /v1/signals/intake endpoint.
"""
import uuid
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.db.models.place import Place

client = TestClient(app)


def _get_active_place_id() -> str:
    """Return the ID of the first active place in the dev DB."""
    db = SessionLocal()
    try:
        place = db.query(Place).filter(Place.is_active.is_(True)).first()
        if place is None:
            pytest.skip("No active places in DB — seed data required")
        return place.id
    finally:
        db.close()


def _unique_event_id() -> str:
    return f"test-event-{uuid.uuid4().hex}"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_intake_signal_valid():
    """Valid signal intake returns 201 with success=True and a signal_id."""
    place_id = _get_active_place_id()
    resp = client.post(
        "/api/v1/signals/intake",
        json={
            "place_id": place_id,
            "signal_type": "award",
            "provider": "michelin",
            "value": 1.0,
            "raw_value": "1 star",
            "external_event_id": _unique_event_id(),
        },
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["success"] is True
    assert data["duplicate"] is False
    assert data["signal_id"] is not None


def test_intake_creator_signal():
    """Creator signal (TikTok) is accepted."""
    place_id = _get_active_place_id()
    resp = client.post(
        "/api/v1/signals/intake",
        json={
            "place_id": place_id,
            "signal_type": "creator",
            "provider": "tiktok",
            "value": 0.8,
            "external_event_id": _unique_event_id(),
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["success"] is True


def test_intake_blog_signal():
    """Blog signal is accepted."""
    place_id = _get_active_place_id()
    resp = client.post(
        "/api/v1/signals/intake",
        json={
            "place_id": place_id,
            "signal_type": "blog",
            "provider": "eater",
            "value": 0.9,
            "external_event_id": _unique_event_id(),
        },
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["success"] is True


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

def test_intake_signal_duplicate():
    """Posting the same (place_id, provider, signal_type, external_event_id) twice
    returns success=True with duplicate=True on the second call."""
    place_id = _get_active_place_id()
    event_id = _unique_event_id()
    payload = {
        "place_id": place_id,
        "signal_type": "award",
        "provider": "michelin",
        "value": 0.7,
        "external_event_id": event_id,
    }
    r1 = client.post("/api/v1/signals/intake", json=payload)
    r2 = client.post("/api/v1/signals/intake", json=payload)

    assert r1.status_code == 201, r1.text
    assert r1.json()["duplicate"] is False

    # Second call: still 201 per spec (success=True, duplicate=True)
    assert r2.status_code == 201, r2.text
    data2 = r2.json()
    assert data2["success"] is True
    assert data2["duplicate"] is True
    assert data2["signal_id"] is None


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

def test_intake_signal_invalid_type():
    """Unknown signal_type returns 400."""
    place_id = _get_active_place_id()
    resp = client.post(
        "/api/v1/signals/intake",
        json={
            "place_id": place_id,
            "signal_type": "NOT_A_TYPE",
            "provider": "internal",
            "value": 0.5,
            "external_event_id": _unique_event_id(),
        },
    )
    assert resp.status_code == 400
    assert "signal_type" in resp.json()["detail"]


def test_intake_signal_invalid_provider():
    """Unknown provider returns 400."""
    place_id = _get_active_place_id()
    resp = client.post(
        "/api/v1/signals/intake",
        json={
            "place_id": place_id,
            "signal_type": "award",
            "provider": "UNKNOWN_PROVIDER",
            "value": 0.5,
            "external_event_id": _unique_event_id(),
        },
    )
    assert resp.status_code == 400
    assert "provider" in resp.json()["detail"]


def test_intake_signal_value_out_of_range():
    """Value > 1.0 is rejected by pydantic validation (422)."""
    place_id = _get_active_place_id()
    resp = client.post(
        "/api/v1/signals/intake",
        json={
            "place_id": place_id,
            "signal_type": "award",
            "provider": "michelin",
            "value": 1.5,
            "external_event_id": _unique_event_id(),
        },
    )
    assert resp.status_code == 422


def test_intake_signal_unknown_place():
    """Non-existent place_id returns 404."""
    resp = client.post(
        "/api/v1/signals/intake",
        json={
            "place_id": "00000000-0000-0000-0000-000000000000",
            "signal_type": "award",
            "provider": "michelin",
            "value": 1.0,
            "external_event_id": _unique_event_id(),
        },
    )
    assert resp.status_code == 404
