"""
Coverage for search_query.py -- specifically the proximity-ordering fix
for a live-reported bug: searching for a real place's name while a city
was selected returned nothing, because search was scoped to that one
city and a match elsewhere in the catalog was filtered out entirely.

The fix has two parts, both covered here: (1) the frontend no longer
sends city_id at all, so a match anywhere in the catalog is found; (2)
when the caller has a location, the SQL query itself orders by distance
(not just rank_score) BEFORE the limit is applied, so a real nearby
match can't be crowded out of the fetch window by unrelated, higher-
rank_score places in other cities -- a plain post-fetch re-rank alone
can't fix that, since it only ever reorders whatever page rank_score
already selected.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.category import Category
from app.db.models.place_categories import place_categories
from app.services.query.search_query import search_places

UNIQUE = uuid.uuid4().hex[:8]
SEARCH_TERM = f"Zzyx{UNIQUE}"


@pytest.fixture
def db():
    created = {"place_ids": [], "city_ids": [], "category_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
        if created["place_ids"]:
            session.execute(
                place_categories.delete().where(
                    place_categories.c.place_id.in_(created["place_ids"])
                )
            )
            session.query(Place).filter(
                Place.id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
        if created["city_ids"]:
            session.query(City).filter(
                City.id.in_(created["city_ids"])
            ).delete(synchronize_session=False)
        if created["category_ids"]:
            session.query(Category).filter(
                Category.id.in_(created["category_ids"])
            ).delete(synchronize_session=False)
        session.commit()
        session.close()


def _make_city(db, created) -> City:
    city = City(
        id=str(uuid.uuid4()), name=f"Search Test City {uuid.uuid4().hex[:6]}",
        slug=f"search-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    created["city_ids"].append(city.id)
    return city


def _make_place(db, created, city, *, name, lat=None, lng=None, rank_score=0.0) -> Place:
    place = Place(name=name, city_id=city.id, lat=lat, lng=lng, rank_score=rank_score)
    db.add(place)
    db.commit()
    created["place_ids"].append(place.id)
    return place


def test_global_search_finds_a_match_outside_the_selected_city(db):
    session, created = db
    city_a = _make_city(session, created)
    city_b = _make_city(session, created)
    match_in_city_b = _make_place(
        session, created, city_b, name=f"{SEARCH_TERM} Kitchen", lat=1.0, lng=1.0
    )

    # No city_id passed -- the whole point of the fix.
    results, total = search_places(session, query=SEARCH_TERM)

    assert match_in_city_b.id in {p.id for p in results}
    assert total == 1


def test_nearby_lower_ranked_match_still_appears_ahead_of_a_distant_higher_ranked_one(db):
    session, created = db
    near_city = _make_city(session, created)
    far_city = _make_city(session, created)

    caller_lat, caller_lng = 37.80, -122.27
    nearby = _make_place(
        session, created, near_city, name=f"{SEARCH_TERM} Near",
        lat=caller_lat + 0.01, lng=caller_lng + 0.01, rank_score=1.0,
    )
    # Many higher-ranked, far-away matches -- enough to fill a small
    # limit purely on rank_score if distance weren't applied at the
    # fetch level.
    for i in range(5):
        _make_place(
            session, created, far_city, name=f"{SEARCH_TERM} Far {i}",
            lat=10.0 + i, lng=10.0 + i, rank_score=9.0,
        )

    results, total = search_places(
        session, query=SEARCH_TERM, lat=caller_lat, lng=caller_lng, limit=3,
    )

    assert total == 6
    assert nearby.id in {p.id for p in results}
    assert results[0].id == nearby.id


def test_without_a_location_falls_back_to_rank_score_ordering(db):
    session, created = db
    city = _make_city(session, created)
    low = _make_place(session, created, city, name=f"{SEARCH_TERM} Low", rank_score=1.0)
    high = _make_place(session, created, city, name=f"{SEARCH_TERM} High", rank_score=9.0)

    results, _ = search_places(session, query=SEARCH_TERM)

    result_ids = [p.id for p in results]
    assert result_ids.index(high.id) < result_ids.index(low.id)


def test_a_place_with_no_coordinates_still_appears_sorted_last(db):
    session, created = db
    city = _make_city(session, created)
    caller_lat, caller_lng = 37.80, -122.27
    with_coords = _make_place(
        session, created, city, name=f"{SEARCH_TERM} HasCoords",
        lat=caller_lat, lng=caller_lng,
    )
    no_coords = _make_place(session, created, city, name=f"{SEARCH_TERM} NoCoords")

    results, total = search_places(session, query=SEARCH_TERM, lat=caller_lat, lng=caller_lng)

    assert total == 2
    result_ids = [p.id for p in results]
    assert result_ids.index(with_coords.id) < result_ids.index(no_coords.id)


def _make_category(session, created, *, name: str) -> Category:
    slug = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
    category = Category(slug=slug, name=name)
    session.add(category)
    session.commit()
    created["category_ids"].append(category.id)
    return category


def test_matches_by_cuisine_category_name_not_just_place_name(db):
    # Confirmed real gap: searching a cuisine/category name previously
    # matched nothing unless a place's own *name* happened to contain
    # that word -- search_places() only ever did Place.name.ilike(...),
    # never touching the category taxonomy at all.
    session, created = db
    city = _make_city(session, created)
    cuisine = _make_category(session, created, name=f"{SEARCH_TERM}Cuisine")
    matched = _make_place(session, created, city, name="Kai", rank_score=1.0)
    session.execute(
        place_categories.insert().values(place_id=matched.id, category_id=cuisine.id)
    )
    session.commit()
    unrelated = _make_place(session, created, city, name="Some Other Place", rank_score=9.0)

    results, total = search_places(session, query=f"{SEARCH_TERM}Cuisine")

    assert total == 1
    assert {p.id for p in results} == {matched.id}
    assert unrelated.id not in {p.id for p in results}


def test_explicit_city_id_still_filters_when_provided(db):
    session, created = db
    city_a = _make_city(session, created)
    city_b = _make_city(session, created)
    in_a = _make_place(session, created, city_a, name=f"{SEARCH_TERM} InA")
    _make_place(session, created, city_b, name=f"{SEARCH_TERM} InB")

    results, total = search_places(session, query=SEARCH_TERM, city_id=city_a.id)

    assert total == 1
    assert results[0].id == in_a.id
