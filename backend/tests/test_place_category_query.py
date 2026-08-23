"""
Coverage for app.services.query.place_category_query, and specifically a
regression test for a real, confirmed production bug: get_categories_for_
places_bulk() selects full Category ORM entities, and Category.places used
to be configured lazy="selectin" (eager). Since nothing in the app ever
reads category.places, that eager load was pure waste -- but a very
expensive kind: every call silently issued extra queries to fully hydrate
every returned category's entire places list (each Place itself carrying
its own eager relationships). This was confirmed live to be the actual
~60-67s stall in the map/geojson endpoint, previously misattributed to the
embedded scheduler.

The regression test below counts real SQL statements executed during a
single get_categories_for_places_bulk() call via a SQLAlchemy engine event
listener -- the only way to actually prove "no hidden extra queries",
since a functional/timing assertion alone wouldn't catch a reintroduced
eager-load on a small enough test dataset to still run fast.
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import event

from app.db.session import SessionLocal, engine
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.category import Category
from app.db.models.place_categories import place_categories
from app.services.query.place_category_query import (
    get_categories_for_place,
    get_categories_for_places_bulk,
)


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


def _make_city(session, created) -> City:
    city = City(
        id=str(uuid.uuid4()), name="Category Query Test City",
        slug=f"category-query-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    session.add(city)
    session.commit()
    created["city_ids"].append(city.id)
    return city


def _make_category(session, created, *, name: str) -> Category:
    slug = f"{name.lower().replace(' ', '-')}-{uuid.uuid4().hex[:8]}"
    category = Category(slug=slug, name=name)
    session.add(category)
    session.commit()
    created["category_ids"].append(category.id)
    return category


def _make_place(session, created, *, city: City, name: str, categories=()) -> Place:
    place = Place(name=name, city_id=city.id, lat=city.lat, lng=city.lng)
    session.add(place)
    session.commit()
    created["place_ids"].append(place.id)
    for category in categories:
        session.execute(
            place_categories.insert().values(place_id=place.id, category_id=category.id)
        )
    session.commit()
    return place


@pytest.fixture
def statement_counter():
    """
    Counts real SQL statements executed on the shared engine while the
    fixture is active. A functional assertion alone ("the right categories
    came back") would pass even with the eager-load bug reintroduced --
    only counting actual round-trips proves there isn't a hidden N+1/select-
    in cascade hiding behind a single logical call.
    """
    count = {"n": 0}

    def _before_cursor_execute(*args, **kwargs):
        count["n"] += 1

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        yield count
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)


def test_bulk_fetch_returns_correct_categories_per_place(db):
    session, created = db
    city = _make_city(session, created)
    italian = _make_category(session, created, name=f"Italian Test {uuid.uuid4().hex[:6]}")
    cafe = _make_category(session, created, name=f"Cafe Test {uuid.uuid4().hex[:6]}")

    place_a = _make_place(session, created, city=city, name="Place A", categories=[italian, cafe])
    place_b = _make_place(session, created, city=city, name="Place B", categories=[cafe])
    place_c = _make_place(session, created, city=city, name="Place C")  # no categories

    result = get_categories_for_places_bulk(
        session, place_ids=[place_a.id, place_b.id, place_c.id]
    )

    assert {c.name for c in result[place_a.id]} == {italian.name, cafe.name}
    assert {c.name for c in result[place_b.id]} == {cafe.name}
    assert place_c.id not in result


def test_bulk_fetch_empty_place_ids_returns_empty_dict(db):
    session, _ = db
    assert get_categories_for_places_bulk(session, place_ids=[]) == {}


def test_single_fetch_returns_categories_sorted_by_name(db):
    session, created = db
    city = _make_city(session, created)
    z_cat = _make_category(session, created, name=f"Zesty Test {uuid.uuid4().hex[:6]}")
    a_cat = _make_category(session, created, name=f"Appetizer Test {uuid.uuid4().hex[:6]}")
    place = _make_place(session, created, city=city, name="Sorted Place", categories=[z_cat, a_cat])

    result = get_categories_for_place(session, place_id=place.id)

    names = [c.name for c in result]
    assert names == sorted(names)


def test_bulk_fetch_issues_exactly_one_query_no_hidden_eager_load(db, statement_counter):
    """
    Regression test for the real production bug: Category.places used to
    be lazy="selectin" (eager) despite nothing in the app ever reading
    category.places. That made every full-Category-entity load silently
    fan out into extra queries hydrating each category's entire places
    list. A category with many associated places made this catastrophic
    in production (~60-67s for the map/geojson endpoint's categories
    lookup alone) -- confirmed via EXPLAIN ANALYZE showing the raw SQL
    itself executes in milliseconds, meaning the cost was entirely in
    SQLAlchemy's post-query ORM hydration, invisible to EXPLAIN ANALYZE.
    """
    session, created = db
    city = _make_city(session, created)
    category = _make_category(session, created, name=f"Popular Test {uuid.uuid4().hex[:6]}")

    # Several places share this one category -- with the eager-load bug,
    # loading this single Category would have triggered a second query
    # pulling in *all* of them (and, transitively, each Place's own eager
    # relationships), not just the one place we're actually asking about.
    places = [
        _make_place(session, created, city=city, name=f"Popular Place {i}", categories=[category])
        for i in range(5)
    ]

    statement_counter["n"] = 0
    get_categories_for_places_bulk(session, place_ids=[places[0].id])

    assert statement_counter["n"] == 1, (
        f"expected exactly 1 SQL statement, got {statement_counter['n']} -- "
        "an eager relationship load is firing extra queries"
    )
