"""
Coverage for GET /place/{id}'s new hours_status/hours_next_change/
hours_raw/outdoor_seating fields -- resolved PlaceTruth rows (written at
promotion time from OSM tags, see test_promotion_pipeline_v2.py) surfaced
through to the response, with live open/closed computed at request time
via app.services.hours.opening_hours_service.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_truth import PlaceTruth

client = TestClient(app)

# San Francisco coordinates -- America/Los_Angeles.
SF_LAT, SF_LNG = 37.7749, -122.4194


def _make_place(*, lat=SF_LAT, lng=SF_LNG, truths: dict[str, str] | None = None) -> str:
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        city = City(
            id=str(uuid.uuid4()), name="Hours Test City",
            slug=f"hours-test-{suffix}", lat=lat, lng=lng, is_active=True,
        )
        db.add(city)
        db.flush()

        place = Place(name="Hours Test Place", city_id=city.id, lat=lat, lng=lng, is_active=True)
        db.add(place)
        db.flush()

        for truth_type, value in (truths or {}).items():
            db.add(PlaceTruth(
                place_id=place.id, truth_type=truth_type, truth_value=value,
                confidence=0.75,
            ))

        db.commit()
        return place.id
    finally:
        db.close()


def test_place_detail_has_no_data_fields_when_no_truths_exist():
    place_id = _make_place()

    response = client.get(f"/api/v1/place/{place_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["hours_status"] is None
    assert body["hours_raw"] is None
    assert body["outdoor_seating"] is None


def test_place_detail_surfaces_outdoor_seating_truth_verbatim():
    place_id = _make_place(truths={"outdoor_seating": "yes"})

    response = client.get(f"/api/v1/place/{place_id}")

    assert response.status_code == 200
    assert response.json()["outdoor_seating"] == "yes"


def test_place_detail_computes_live_hours_status_from_truth():
    place_id = _make_place(truths={"hours": "24/7"})

    response = client.get(f"/api/v1/place/{place_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["hours_status"] == "open"
    assert body["hours_raw"] == "24/7"


def test_place_detail_reports_unknown_not_a_crash_for_malformed_hours_truth():
    place_id = _make_place(truths={"hours": "not a real schedule at all ###"})

    response = client.get(f"/api/v1/place/{place_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["hours_status"] is None
    assert body["hours_raw"] == "not a real schedule at all ###"
