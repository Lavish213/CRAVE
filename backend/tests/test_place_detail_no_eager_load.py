"""
Regression test for the same bug class fixed in
get_categories_for_places_bulk() (see test_place_category_query.py), found
in a second place while auditing every lazy="selectin" relationship on
Place: GET /api/v1/place/{place_id} loaded the full Place ORM entity via
select(Place), which -- per the model's own relationship config --
silently triggered eager selectin loads of Place.city, Place.claims,
Place.truths, and Place.images on every single request, none of which the
response ever reads (images and categories are both re-fetched via
separate, correctly-scoped queries a few lines later). This is one of the
most frequently-hit endpoints in the app (every place-detail screen view),
so the wasted queries here were paid far more often than the map bug's.

Fixed by selecting specific scalar columns instead of the full entity
(the same pattern app/services/query/map_query.py already used
successfully) rather than touching the model's relationship defaults --
Place.categories genuinely is read elsewhere in the app (confirmed via
grep: promote_service_v2.py, ranking_service.py), so its eager default
stays; this fix only changes what this one route selects.
"""
from __future__ import annotations

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import event

from app.main import app
from app.db.session import SessionLocal, engine
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage, VISIBILITY_SHOWCASE

client = TestClient(app)


def _make_place_with_images(*, image_count: int) -> str:
    db = SessionLocal()
    try:
        suffix = uuid.uuid4().hex[:8]
        city = City(
            id=str(uuid.uuid4()), name="No Eager Load Test City",
            slug=f"no-eager-load-test-{suffix}", lat=37.8, lng=-122.27, is_active=True,
        )
        db.add(city)
        db.flush()

        place = Place(name="No Eager Load Test Place", city_id=city.id, is_active=True)
        db.add(place)
        db.flush()

        for i in range(image_count):
            db.add(PlaceImage(
                place_id=place.id,
                url=f"https://example.com/no-eager-load-{i}.jpg",
                is_primary=(i == 0),
                visibility_status=VISIBILITY_SHOWCASE,
            ))

        db.commit()
        return place.id
    finally:
        db.close()


def test_place_detail_returns_correct_response_shape():
    place_id = _make_place_with_images(image_count=2)

    response = client.get(f"/api/v1/place/{place_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == place_id
    assert len(body["images"]) == 2
    assert body["primary_image_url"] == body["images"][0]


def test_place_detail_issues_a_small_bounded_number_of_queries():
    """
    Regression guard for the eager-load bug: this must stay a small,
    constant number of statements (place + gallery images + categories)
    regardless of how many claims/truths rows a real place accumulates
    over its lifetime. Before the fix, loading the full Place entity added
    4 more statements here (city, claims, truths, images all eagerly
    selectin-loaded) on every single request to one of the most
    frequently-hit endpoints in the app.
    """
    place_id = _make_place_with_images(image_count=1)

    count = {"n": 0}

    def _before_cursor_execute(*args, **kwargs):
        count["n"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        response = client.get(f"/api/v1/place/{place_id}")
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)

    assert response.status_code == 200
    assert count["n"] <= 4, (
        f"expected at most 4 SQL statements (place + gallery + categories, "
        f"plus headroom), got {count['n']} -- a full-entity load may have "
        "reintroduced eager relationship queries"
    )
