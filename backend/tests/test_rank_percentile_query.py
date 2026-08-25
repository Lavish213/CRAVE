"""
Coverage for rank_percentile_query.py -- the fix for the Search screen's
"everything is either Hidden Gem or Worth Knowing" bug.

Root cause: place_score_v4's structural bucket is capped at 0.28, and most
normally-populated places hit that cap, so absolute rank_score thresholds
in scoring.ts's getTier() clustered nearly the whole catalog into two
adjacent tiers. The fix moves tiering onto each place's percentile
standing within its own city (backed by CityPlaceRanking, already
computed hourly) instead of an absolute score. These tests cover the
percentile math itself, independent of the tier-boundary choice made in
scoring.ts/places.py.
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
from app.db.models.city_place_ranking import CityPlaceRanking
from app.services.query.rank_percentile_query import get_rank_percentiles


@pytest.fixture
def db():
    created = {"place_ids": [], "city_ids": [], "ranking_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
        if created["ranking_ids"]:
            session.query(CityPlaceRanking).filter(
                CityPlaceRanking.id.in_(created["ranking_ids"])
            ).delete(synchronize_session=False)
        if created["place_ids"]:
            session.query(Place).filter(
                Place.id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
        if created["city_ids"]:
            session.query(City).filter(
                City.id.in_(created["city_ids"])
            ).delete(synchronize_session=False)
        session.commit()
        session.close()


def _make_city(db, created) -> City:
    city = City(
        id=str(uuid.uuid4()), name=f"Percentile Test City {uuid.uuid4().hex[:6]}",
        slug=f"percentile-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    created["city_ids"].append(city.id)
    return city


def _make_place(db, created, city, *, name="Test Place") -> Place:
    place = Place(name=name, city_id=city.id, rank_score=0.0)
    db.add(place)
    db.commit()
    created["place_ids"].append(place.id)
    return place


def _make_ranking(db, created, *, city, place, rank_position) -> CityPlaceRanking:
    ranking = CityPlaceRanking(
        city_id=city.id, place_id=place.id,
        rank_position=rank_position, rank_score=0.5,
    )
    db.add(ranking)
    db.commit()
    created["ranking_ids"].append(ranking.id)
    return ranking


def test_empty_place_ids_returns_empty_dict(db):
    session, _ = db
    assert get_rank_percentiles(session, place_ids=[]) == {}


def test_best_place_in_city_gets_percentile_one(db):
    session, created = db
    city = _make_city(session, created)
    places = [_make_place(session, created, city, name=f"P{i}") for i in range(5)]
    for i, place in enumerate(places):
        _make_ranking(session, created, city=city, place=place, rank_position=i + 1)

    percentiles = get_rank_percentiles(session, place_ids=[p.id for p in places])

    assert percentiles[places[0].id] == pytest.approx(1.0)


def test_worst_place_in_city_gets_percentile_zero(db):
    session, created = db
    city = _make_city(session, created)
    places = [_make_place(session, created, city, name=f"P{i}") for i in range(5)]
    for i, place in enumerate(places):
        _make_ranking(session, created, city=city, place=place, rank_position=i + 1)

    percentiles = get_rank_percentiles(session, place_ids=[p.id for p in places])

    assert percentiles[places[-1].id] == pytest.approx(0.0)


def test_percentiles_spread_evenly_across_a_city(db):
    session, created = db
    city = _make_city(session, created)
    places = [_make_place(session, created, city, name=f"P{i}") for i in range(5)]
    for i, place in enumerate(places):
        _make_ranking(session, created, city=city, place=place, rank_position=i + 1)

    percentiles = get_rank_percentiles(session, place_ids=[p.id for p in places])

    # 5 places, 1-indexed rank_position 1..5 -> percentiles 1.0, 0.75, 0.5, 0.25, 0.0
    expected = [1.0, 0.75, 0.5, 0.25, 0.0]
    for place, exp in zip(places, expected):
        assert percentiles[place.id] == pytest.approx(exp)


def test_sole_place_in_a_city_gets_percentile_one(db):
    session, created = db
    city = _make_city(session, created)
    place = _make_place(session, created, city)
    _make_ranking(session, created, city=city, place=place, rank_position=1)

    percentiles = get_rank_percentiles(session, place_ids=[place.id])

    assert percentiles[place.id] == pytest.approx(1.0)


def test_place_with_no_ranking_snapshot_is_absent_from_result(db):
    session, created = db
    city = _make_city(session, created)
    unranked_place = _make_place(session, created, city)

    percentiles = get_rank_percentiles(session, place_ids=[unranked_place.id])

    assert unranked_place.id not in percentiles


def test_percentiles_are_computed_independently_per_city(db):
    session, created = db
    city_a = _make_city(session, created)
    city_b = _make_city(session, created)

    # City A: 2 places. City B: 4 places. A place's percentile must reflect
    # only its own city's ranking, not the combined pool across both.
    a_places = [_make_place(session, created, city_a, name=f"A{i}") for i in range(2)]
    b_places = [_make_place(session, created, city_b, name=f"B{i}") for i in range(4)]

    for i, place in enumerate(a_places):
        _make_ranking(session, created, city=city_a, place=place, rank_position=i + 1)
    for i, place in enumerate(b_places):
        _make_ranking(session, created, city=city_b, place=place, rank_position=i + 1)

    all_ids = [p.id for p in a_places] + [p.id for p in b_places]
    percentiles = get_rank_percentiles(session, place_ids=all_ids)

    # City A's 2nd-place finisher (last of 2) is worst in its own city -> 0.0,
    # even though city B has finishers 3rd and 4th out of a bigger pool.
    assert percentiles[a_places[1].id] == pytest.approx(0.0)
    assert percentiles[b_places[1].id] == pytest.approx(2 / 3)
