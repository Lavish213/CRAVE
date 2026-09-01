# tests/trending/test_trending.py
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from app.main import app
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_video import PlaceVideo, STATUS_APPROVED, MOD_APPROVED

client = TestClient(app)


def _get_a_city_with_places() -> str | None:
    """Return a city_id that has at least one active place, or None."""
    from app.db.session import SessionLocal
    db = SessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT city_id FROM places WHERE is_active=true "
                "GROUP BY city_id ORDER BY COUNT(*) DESC LIMIT 1"
            )
        ).fetchone()
        return row[0] if row else None
    finally:
        db.close()


def test_trending_returns_places():
    """Trending endpoint returns a valid response for a city that has places."""
    city_id = _get_a_city_with_places()
    if city_id is None:
        pytest.skip("No active places in DB — cannot test trending")

    response = client.get(f"/api/v1/trending?city_id={city_id}")
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    assert "page" in data
    assert "page_size" in data
    assert data["total"] >= 1
    assert len(data["items"]) >= 1


def test_trending_structure():
    """Each trending item has required place fields."""
    city_id = _get_a_city_with_places()
    if city_id is None:
        pytest.skip("No active places in DB — cannot test trending")

    response = client.get(f"/api/v1/trending?city_id={city_id}&limit=5")
    assert response.status_code == 200
    data = response.json()

    for item in data["items"]:
        assert "id" in item
        assert "name" in item
        assert "city_id" in item
        assert "rank_score" in item
        assert item["city_id"] == city_id


def test_trending_empty_city():
    """Trending endpoint returns empty list for unknown city_id."""
    response = client.get("/api/v1/trending?city_id=00000000-0000-0000-0000-000000000000")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 0
    assert data["items"] == []


def test_trending_limit_respected():
    """Trending endpoint respects the limit parameter."""
    city_id = _get_a_city_with_places()
    if city_id is None:
        pytest.skip("No active places in DB — cannot test trending")

    response = client.get(f"/api/v1/trending?city_id={city_id}&limit=3")
    assert response.status_code == 200
    data = response.json()
    assert len(data["items"]) <= 3


def test_trending_invalid_city_id_format():
    """Trending endpoint with missing city_id returns 422."""
    response = client.get("/api/v1/trending")
    assert response.status_code == 422


def test_trending_reports_approved_visible_video():
    """
    Route-level coverage for has_video wiring specifically through
    GET /trending -- the underlying PlaceOut/_inject_category mechanism
    is already proven in test_place_video_presence.py, but nothing
    exercised this route end-to-end (gap flagged during review of PR
    #109). Uses its own fresh city/place, not ambient DB state, so a
    fresh city_id also sidesteps the 5-minute response cache.
    """
    db = SessionLocal()
    city_id = str(uuid.uuid4())
    place_id = str(uuid.uuid4())
    try:
        db.add(City(
            id=city_id, name="Trending Video Test City",
            slug=f"trending-video-test-{city_id[:8]}",
            lat=37.0, lng=-122.0, is_active=True,
        ))
        db.add(Place(
            id=place_id, name="Trending Video Test Place", city_id=city_id,
            lat=37.0, lng=-122.0, is_active=True, rank_score=0.5,
        ))
        db.commit()
        db.add(PlaceVideo(
            place_id=place_id, uploaded_by=f"user-{uuid.uuid4().hex[:8]}",
            status=STATUS_APPROVED, moderation_status=MOD_APPROVED,
        ))
        db.commit()

        resp = client.get(f"/api/v1/trending?city_id={city_id}")
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["has_video"] is True
    finally:
        db.query(PlaceVideo).filter(PlaceVideo.place_id == place_id).delete(
            synchronize_session=False
        )
        db.query(Place).filter(Place.id == place_id).delete(synchronize_session=False)
        db.query(City).filter(City.id == city_id).delete(synchronize_session=False)
        db.commit()
        db.close()


def test_trending_cached_response():
    """Two requests to the same city return the same result (from cache on 2nd)."""
    city_id = _get_a_city_with_places()
    if city_id is None:
        pytest.skip("No active places in DB — cannot test trending")

    r1 = client.get(f"/api/v1/trending?city_id={city_id}&limit=10")
    r2 = client.get(f"/api/v1/trending?city_id={city_id}&limit=10")
    assert r1.status_code == 200
    assert r2.status_code == 200
    # Same items returned
    assert r1.json()["items"] == r2.json()["items"]
