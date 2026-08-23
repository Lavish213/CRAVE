"""
Coverage for get_taste_profile — CRAVE's equivalent of Beli's own
"Taste Profile" stats screen (total places ranked, tier breakdown,
favorite cuisine, top city, percentile), confirmed via research to be a
real, advertised feature of a direct competitor and built here as pure
aggregation over data CRAVE already has.
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
from app.db.models.place_ranking import PlaceRanking
from app.services.social.taste_profile_service import get_taste_profile


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
            session.query(PlaceRanking).filter(
                PlaceRanking.place_id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
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


def _make_city(session, created, *, name: str) -> City:
    city = City(
        id=str(uuid.uuid4()), name=name,
        slug=f"taste-profile-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    session.add(city)
    session.commit()
    created["city_ids"].append(city.id)
    return city


def _get_or_create_category(session, created, *, name: str) -> Category:
    # Category.name is globally unique, and a real seeded category by
    # this exact name (especially a generic one like "Restaurant", or a
    # common cuisine like "Italian") may well already exist in the shared
    # test DB — reuse it rather than risk a uniqueness collision. Only
    # newly-created categories go in `created` for teardown; a reused
    # one isn't ours to delete.
    existing = session.query(Category).filter(Category.name == name).one_or_none()
    if existing:
        return existing
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


def _rank(session, *, user_id: str, place: Place, tier: str) -> None:
    session.add(PlaceRanking(user_id=user_id, place_id=place.id, tier=tier, rank_score=5.0))
    session.commit()


def test_totals_and_tier_counts(db):
    session, created = db
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    city = _make_city(session, created, name="Totals Test City")
    p1 = _make_place(session, created, city=city, name="Place 1")
    p2 = _make_place(session, created, city=city, name="Place 2")
    p3 = _make_place(session, created, city=city, name="Place 3")
    _rank(session, user_id=user_id, place=p1, tier="liked")
    _rank(session, user_id=user_id, place=p2, tier="liked")
    _rank(session, user_id=user_id, place=p3, tier="disliked")

    result = get_taste_profile(session, user_id=user_id)

    assert result["total_ranked"] == 3
    assert result["tier_counts"] == {"liked": 2, "fine": 0, "disliked": 1}


def test_favorite_cuisine_prefers_liked_places(db):
    session, created = db
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    city = _make_city(session, created, name="Cuisine Test City")
    italian = _get_or_create_category(session, created, name="Italian")
    thai = _get_or_create_category(session, created, name="Thai")

    liked_italian = _make_place(session, created, city=city, name="Liked Italian", categories=[italian])
    disliked_thai = _make_place(session, created, city=city, name="Disliked Thai x3", categories=[thai])
    _rank(session, user_id=user_id, place=liked_italian, tier="liked")
    _rank(session, user_id=user_id, place=disliked_thai, tier="disliked")

    result = get_taste_profile(session, user_id=user_id)

    # Thai appears in a disliked place only; Italian is the sole liked
    # cuisine, so it must win even though it has fewer total rankings.
    assert result["favorite_cuisine"] == "Italian"


def test_favorite_cuisine_falls_back_to_all_ranked_places_with_no_likes(db):
    session, created = db
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    city = _make_city(session, created, name="Fallback Cuisine Test City")
    mexican = _get_or_create_category(session, created, name="Mexican")
    p1 = _make_place(session, created, city=city, name="Fine Mexican 1", categories=[mexican])
    p2 = _make_place(session, created, city=city, name="Fine Mexican 2", categories=[mexican])
    _rank(session, user_id=user_id, place=p1, tier="fine")
    _rank(session, user_id=user_id, place=p2, tier="fine")

    result = get_taste_profile(session, user_id=user_id)

    assert result["favorite_cuisine"] == "Mexican"


def test_favorite_cuisine_excludes_generic_categories(db):
    session, created = db
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    city = _make_city(session, created, name="Generic Cuisine Test City")
    generic = _get_or_create_category(session, created, name="Restaurant")
    specific = _get_or_create_category(session, created, name="Korean")
    place = _make_place(
        session, created, city=city, name="Korean Restaurant",
        categories=[generic, specific],
    )
    _rank(session, user_id=user_id, place=place, tier="liked")

    result = get_taste_profile(session, user_id=user_id)

    assert result["favorite_cuisine"] == "Korean"


def test_top_city_is_the_city_with_the_most_ranked_places(db):
    session, created = db
    user_id = f"user-{uuid.uuid4().hex[:8]}"
    home_city = _make_city(session, created, name="Home City")
    away_city = _make_city(session, created, name="Away City")
    _rank(session, user_id=user_id, place=_make_place(session, created, city=home_city, name="Home 1"), tier="liked")
    _rank(session, user_id=user_id, place=_make_place(session, created, city=home_city, name="Home 2"), tier="liked")
    _rank(session, user_id=user_id, place=_make_place(session, created, city=away_city, name="Away 1"), tier="liked")

    result = get_taste_profile(session, user_id=user_id)

    assert result["top_city"]["name"] == "Home City"
    assert result["top_city"]["count"] == 2


def test_percentile_reflects_standing_among_other_ranked_users(db):
    session, created = db
    me = f"user-{uuid.uuid4().hex[:8]}"
    behind_me = f"user-{uuid.uuid4().hex[:8]}"
    ahead_of_me = f"user-{uuid.uuid4().hex[:8]}"
    city = _make_city(session, created, name="Percentile Test City")

    _rank(session, user_id=me, place=_make_place(session, created, city=city, name="Me 1"), tier="liked")
    _rank(session, user_id=me, place=_make_place(session, created, city=city, name="Me 2"), tier="liked")

    _rank(session, user_id=behind_me, place=_make_place(session, created, city=city, name="Behind 1"), tier="liked")

    for i in range(5):
        _rank(session, user_id=ahead_of_me, place=_make_place(session, created, city=city, name=f"Ahead {i}"), tier="liked")

    result = get_taste_profile(session, user_id=me)

    # Exactly one of the two "other" users (behind_me) ranked <= my count.
    assert result["percentile"] == 50


def test_percentile_is_none_when_user_has_ranked_nothing(db):
    session, _created = db
    result = get_taste_profile(session, user_id=f"user-{uuid.uuid4().hex[:8]}")
    assert result["percentile"] is None
    assert result["total_ranked"] == 0
    assert result["favorite_cuisine"] is None
    assert result["top_city"] is None
