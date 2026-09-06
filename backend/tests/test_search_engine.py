"""
Coverage for search_engine.py's execute_search() -- specifically a
confirmed real bug: search_query.py's SQL fetch applies LIMIT/OFFSET
using only rank_score/distance, but rank_search_results() (search_ranker.
py) re-scores with exact-match/menu/proximity boosts *after* that. A
result that would win after enrichment could never surface at all if it
didn't already make the raw-ordered page window -- pagination was
cutting before ranking, not after it.

The fix widens the candidate fetch (execute_search's own pool_limit,
capped like search_query.py's fuzzy-fallback pool) so enrichment has
room to actually promote a result into the visible page.
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
from app.services.search.search_engine import execute_search

UNIQUE = uuid.uuid4().hex[:8]
SEARCH_TERM = f"Zzyx{UNIQUE}"


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
        id=str(uuid.uuid4()), name=f"Search Engine Test City {uuid.uuid4().hex[:6]}",
        slug=f"search-engine-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    created["city_ids"].append(city.id)
    return city


def _make_place(db, created, city, *, name, rank_score, has_menu=False) -> Place:
    place = Place(name=name, city_id=city.id, rank_score=rank_score)
    place.has_menu = has_menu
    db.add(place)
    db.commit()
    created["place_ids"].append(place.id)
    return place


def test_a_result_that_wins_after_enrichment_survives_pagination(db):
    session, created = db
    city = _make_city(session, created)
    # An exact-name match with has_menu -- search_ranker.py's own boosts
    # (0.10 exact + 0.05 menu = +0.15) -- but the *lowest* raw rank_score
    # of the set, so it sorts dead last in search_query.py's raw SQL
    # order (rank_score DESC), which is what a naive small page would cut
    # on before enrichment ever runs.
    winner = _make_place(
        session, created, city, name=SEARCH_TERM, rank_score=0.10, has_menu=True,
    )
    # Filler names deliberately don't *start with* the search term (only
    # contain it, via ilike's leading '%') -- search_ranker.py's own
    # exact/prefix-match boost only fires on a true prefix, so these get
    # no name-based boost at all and this margin stays clean: each
    # filler's rank_score sits between winner's raw score (0.10) and its
    # post-enrichment total (0.25), so raw order ranks every filler above
    # winner, but enrichment flips that.
    for i in range(5):
        _make_place(
            session, created, city, name=f"Diner {i} near {SEARCH_TERM}", rank_score=0.15 + i / 100,
        )

    results, total = execute_search(session, query=SEARCH_TERM, limit=3, offset=0)

    assert total == 6
    assert winner.id in {p.id for p in results}
    # Exact match + menu boost (0.15) on top of winner's 0.10 base (0.25
    # total) beats every filler's higher-but-still-under-0.25 base
    # rank_score (0.15-0.19, no boost of their own) once enrichment is
    # applied -- it should be first.
    assert results[0].id == winner.id


def test_pagination_slices_the_ranked_result_not_the_raw_sql_order(db):
    session, created = db
    city = _make_city(session, created)
    first = _make_place(session, created, city, name=SEARCH_TERM, rank_score=0.10, has_menu=True)
    for i in range(3):
        _make_place(session, created, city, name=f"Diner {i} near {SEARCH_TERM}", rank_score=0.15 + i / 100)

    page1, total = execute_search(session, query=SEARCH_TERM, limit=2, offset=0)
    page2, _ = execute_search(session, query=SEARCH_TERM, limit=2, offset=2)

    assert total == 4
    assert page1[0].id == first.id
    # No overlap between pages, and every result accounted for exactly once.
    page1_ids = {p.id for p in page1}
    page2_ids = {p.id for p in page2}
    assert page1_ids.isdisjoint(page2_ids)
    assert len(page1_ids) + len(page2_ids) == 4


def test_a_page_at_offset_beyond_100_is_not_silently_empty(db):
    # Regression test for a real bug in an earlier version of this fix:
    # execute_search()'s widened pool_limit (up to 500) was silently
    # truncated back down to search_query.py's public MAX_LIMIT (100) by
    # search_places()'s own _clamp_limit(), since execute_search wasn't
    # yet passing the max_limit= override. Any page with offset >= 100
    # then sliced into a candidate list shorter than the requested
    # offset and returned an empty page while total_count still reported
    # the real (larger) match count.
    session, created = db
    city = _make_city(session, created)
    for i in range(110):
        _make_place(session, created, city, name=f"{SEARCH_TERM} {i:03d}", rank_score=i / 110)

    results, total = execute_search(session, query=SEARCH_TERM, limit=10, offset=105)

    assert total == 110
    assert len(results) == 5  # only 5 remain past offset 105 of 110 total
    assert len(results) > 0
