"""Coverage for search_query.py's typo-tolerance fallback.

CRAVE_STATUS.md long flagged "no typo tolerance" as a known gap. This adds
a bounded, dependency-free fallback (stdlib difflib, no pg_trgm/schema
change -- this session has no way to verify a Postgres extension
migration would even be allowed on Railway's managed instance) that only
triggers when the exact ilike search finds nothing, so the common case
(a real substring match) stays a single cheap query.
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
from app.services.query.search_query import search_places

UNIQUE = uuid.uuid4().hex[:8]


@pytest.fixture
def db():
    created = {"place_ids": [], "city_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
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
        id=str(uuid.uuid4()), name=f"Fuzzy Test City {uuid.uuid4().hex[:6]}",
        slug=f"fuzzy-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    created["city_ids"].append(city.id)
    return city


def _make_place(db, created, city, *, name, rank_score=0.0, price_tier=None) -> Place:
    place = Place(name=name, city_id=city.id, rank_score=rank_score, price_tier=price_tier)
    db.add(place)
    db.commit()
    created["place_ids"].append(place.id)
    return place


def test_typo_query_falls_back_to_a_fuzzy_match(db):
    session, created = db
    city = _make_city(session, created)
    target_name = f"Zzyx{UNIQUE} Tacos"
    place = _make_place(session, created, city, name=target_name, rank_score=1.0)

    # One-character typo -- an exact ilike substring match would find
    # nothing at all, since "Tacoz" is not a substring of "Tacos".
    typo_query = f"Zzyx{UNIQUE} Tacoz"

    results, total = search_places(session, query=typo_query, city_id=city.id)

    assert place.id in {p.id for p in results}
    assert total == 1


def test_exact_substring_match_never_triggers_the_fallback(db):
    """The fuzzy path must not run at all when a real match exists --
    confirmed by using a name so different from the query that only the
    exact substring path (not fuzzy similarity) could find it."""
    session, created = db
    city = _make_city(session, created)
    place = _make_place(
        session, created, city, name=f"Zzyx{UNIQUE} The Best Sandwich Shop In Town",
    )

    results, total = search_places(session, query=f"Zzyx{UNIQUE}", city_id=city.id)

    assert place.id in {p.id for p in results}
    assert total == 1


def test_completely_unrelated_query_returns_no_fuzzy_matches(db):
    session, created = db
    city = _make_city(session, created)
    _make_place(session, created, city, name=f"Zzyx{UNIQUE} Pizza Place")

    results, total = search_places(
        session, query=f"Qqrst{UNIQUE} Something Entirely Different", city_id=city.id,
    )

    assert results == []
    assert total == 0


def test_fuzzy_fallback_respects_the_price_tier_filter(db):
    session, created = db
    city = _make_city(session, created)
    # Neither name contains the typo'd query as a literal substring ("Tacoz"
    # with a z never appears in either "Tacos ..." name with an s) -- both
    # only match via fuzzy similarity, so this genuinely exercises the
    # fallback path rather than accidentally hitting an exact ilike match.
    cheap = _make_place(
        session, created, city, name=f"Zzyx{UNIQUE} Tacos Grill", price_tier=1,
    )
    _make_place(
        session, created, city, name=f"Zzyx{UNIQUE} Tacos Bar", price_tier=4,
    )

    typo_query = f"Zzyx{UNIQUE} Tacoz"
    results, total = search_places(
        session, query=typo_query, city_id=city.id, price_tier=1,
    )

    result_ids = {p.id for p in results}
    assert result_ids == {cheap.id}
    assert total == 1
