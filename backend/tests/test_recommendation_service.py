"""
Coverage for recommendation_service.py -- the collaborative-filtering
recommendations feed (Beli's "prediction score" equivalent) and the
Match Score taste-compatibility number it shares its similarity
computation with.
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
from app.db.models.place_ranking import PlaceRanking
from app.db.models.hitlist_save import HitlistSave
from app.db.models.user_block import UserBlock
from app.services.social.recommendation_service import get_recommendations, get_match_score


@pytest.fixture
def db():
    # Same created-row tracking/teardown convention as
    # test_friend_rankings_service.py -- an uncleaned Place row (rank_score
    # 0.0, zero images) can pollute test_image_worker_starvation.py's own
    # unscoped query depending on file run order.
    created = {"place_ids": [], "city_ids": []}
    session = SessionLocal()
    try:
        yield session, created
    finally:
        session.rollback()
        if created["place_ids"]:
            session.query(HitlistSave).filter(
                HitlistSave.place_id.in_(created["place_ids"])
            ).delete(synchronize_session=False)
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
        session.commit()
        session.close()


def _make_place(db, created, *, rank_score: float = 0.0) -> Place:
    city = City(
        id=str(uuid.uuid4()), name="Recs Test City",
        slug=f"recs-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    created["city_ids"].append(city.id)
    place = Place(
        name=f"Recs Test Place {uuid.uuid4().hex[:6]}",
        city_id=city.id, lat=37.8, lng=-122.27, rank_score=rank_score,
    )
    db.add(place)
    db.commit()
    created["place_ids"].append(place.id)
    return place


def _rank(db, *, user_id: str, place: Place, tier: str, score: float) -> None:
    db.add(PlaceRanking(user_id=user_id, place_id=place.id, tier=tier, rank_score=score))
    db.commit()


def _save(db, *, user_id: str, place: Place) -> None:
    db.add(
        HitlistSave(
            user_id=user_id,
            place_name=place.name,
            place_id=place.id,
            resolution_status="resolved",
            dedup_key=f"save:{user_id}:{place.id}",
        )
    )
    db.commit()


def test_cold_start_returns_top_rated_places_when_user_has_no_rankings(db):
    session, created = db
    me = f"me_{uuid.uuid4().hex[:8]}"
    low = _make_place(session, created, rank_score=2.0)
    high = _make_place(session, created, rank_score=9.0)

    result = get_recommendations(session, user_id=me, limit=10)

    result_ids = [p.id for p in result]
    assert result_ids.index(high.id) < result_ids.index(low.id)


def test_cold_start_excludes_places_already_ranked_or_saved(db):
    session, created = db
    me = f"me_{uuid.uuid4().hex[:8]}"
    ranked = _make_place(session, created, rank_score=9.0)
    saved = _make_place(session, created, rank_score=8.5)
    unranked = _make_place(session, created, rank_score=5.0)
    _rank(session, user_id=me, place=ranked, tier="liked", score=8.0)
    _save(session, user_id=me, place=saved)

    result = get_recommendations(session, user_id=me, limit=10)

    result_ids = {p.id for p in result}
    assert ranked.id not in result_ids
    assert saved.id not in result_ids
    assert unranked.id in result_ids


def test_recommends_a_place_liked_by_a_similar_user(db):
    session, created = db
    me = f"me_{uuid.uuid4().hex[:8]}"
    twin = f"twin_{uuid.uuid4().hex[:8]}"

    shared_a = _make_place(session, created)
    shared_b = _make_place(session, created)
    twins_pick = _make_place(session, created)

    # Same tastes on two shared places -> high similarity.
    _rank(session, user_id=me, place=shared_a, tier="liked", score=9.0)
    _rank(session, user_id=twin, place=shared_a, tier="liked", score=9.0)
    _rank(session, user_id=me, place=shared_b, tier="fine", score=5.0)
    _rank(session, user_id=twin, place=shared_b, tier="fine", score=5.0)
    # Twin also loves a place I haven't ranked yet.
    _rank(session, user_id=twin, place=twins_pick, tier="liked", score=9.5)

    result = get_recommendations(session, user_id=me, limit=10)

    assert twins_pick.id in {p.id for p in result}


def test_a_single_shared_place_is_not_enough_to_count_as_similar(db):
    session, created = db
    me = f"me_{uuid.uuid4().hex[:8]}"
    stranger = f"stranger_{uuid.uuid4().hex[:8]}"

    shared = _make_place(session, created)
    decoy = _make_place(session, created, rank_score=9.0)
    strangers_pick = _make_place(session, created, rank_score=0.5)

    _rank(session, user_id=me, place=shared, tier="liked", score=9.0)
    _rank(session, user_id=stranger, place=shared, tier="liked", score=9.0)
    _rank(session, user_id=stranger, place=strangers_pick, tier="liked", score=9.9)

    result = get_recommendations(session, user_id=me, limit=10)
    result_ids = [p.id for p in result]

    # Only one shared ranked place -- below MIN_SHARED_PLACES, so stranger
    # never counts as "similar" and strangers_pick's very high
    # PlaceRanking score from them never becomes a collaborative-filtering
    # weight. If it wrongly did, strangers_pick would jump to the very top
    # of the list (a real similarity match always outranks a cold-start
    # backfill) -- ahead of decoy, whose own intrinsic rank_score (9.0) is
    # otherwise clearly higher than strangers_pick's (0.5).
    assert decoy.id in result_ids
    if strangers_pick.id in result_ids:
        assert result_ids.index(decoy.id) < result_ids.index(strangers_pick.id)


def test_excludes_recommendations_sourced_from_a_blocked_user(db):
    session, created = db
    me = f"me_{uuid.uuid4().hex[:8]}"
    blocked = f"blocked_{uuid.uuid4().hex[:8]}"

    shared_a = _make_place(session, created)
    shared_b = _make_place(session, created)
    decoy = _make_place(session, created, rank_score=9.0)
    blocked_pick = _make_place(session, created, rank_score=0.5)

    _rank(session, user_id=me, place=shared_a, tier="liked", score=9.0)
    _rank(session, user_id=blocked, place=shared_a, tier="liked", score=9.0)
    _rank(session, user_id=me, place=shared_b, tier="fine", score=5.0)
    _rank(session, user_id=blocked, place=shared_b, tier="fine", score=5.0)
    _rank(session, user_id=blocked, place=blocked_pick, tier="liked", score=9.5)

    session.add(UserBlock(blocker_id=me, blocked_id=blocked))
    session.commit()
    try:
        result = get_recommendations(session, user_id=me, limit=10)
        result_ids = [p.id for p in result]
        # `blocked` shares 2 ranked places with me at matching scores --
        # enough to normally count as a similar user -- and rated
        # blocked_pick very highly. If blocking weren't enforced here,
        # that collaborative-filtering weight would put blocked_pick
        # ahead of decoy despite decoy's much higher real rank_score
        # (a similarity-sourced pick always outranks a cold-start
        # backfill pick).
        assert decoy.id in result_ids
        if blocked_pick.id in result_ids:
            assert result_ids.index(decoy.id) < result_ids.index(blocked_pick.id)
    finally:
        session.query(UserBlock).filter(
            UserBlock.blocker_id == me, UserBlock.blocked_id == blocked
        ).delete(synchronize_session=False)
        session.commit()


def test_match_score_none_when_users_share_too_few_ranked_places(db):
    session, created = db
    a = f"a_{uuid.uuid4().hex[:8]}"
    b = f"b_{uuid.uuid4().hex[:8]}"
    place = _make_place(session, created)
    _rank(session, user_id=a, place=place, tier="liked", score=9.0)
    _rank(session, user_id=b, place=place, tier="liked", score=9.0)

    assert get_match_score(session, user_id=a, other_user_id=b) is None


def test_match_score_high_for_closely_aligned_tastes(db):
    session, created = db
    a = f"a_{uuid.uuid4().hex[:8]}"
    b = f"b_{uuid.uuid4().hex[:8]}"
    p1 = _make_place(session, created)
    p2 = _make_place(session, created)

    _rank(session, user_id=a, place=p1, tier="liked", score=9.0)
    _rank(session, user_id=b, place=p1, tier="liked", score=9.0)
    _rank(session, user_id=a, place=p2, tier="fine", score=5.0)
    _rank(session, user_id=b, place=p2, tier="fine", score=5.0)

    score = get_match_score(session, user_id=a, other_user_id=b)
    assert score is not None
    assert score >= 95


def test_match_score_none_for_self(db):
    session, created = db
    a = f"a_{uuid.uuid4().hex[:8]}"
    place = _make_place(session, created)
    _rank(session, user_id=a, place=place, tier="liked", score=9.0)

    assert get_match_score(session, user_id=a, other_user_id=a) is None
