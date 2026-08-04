"""
Coverage for app.services.personal_ranking.ranking_service — the actual
differentiating mechanic: mark a place visited, pick a tier, then answer
binary-insertion "which was better" comparisons until the new place lands
in a precise position, deriving a 0-10 score from where it landed.
Reverse-engineered from how Beli's own flow works (tiers: "liked" / "fine"
/ "disliked"; see PlaceRanking's TIER_SCORE_BANDS for the score bands this
app uses, which are this app's own convention, not Beli's literal formula).
"""
from __future__ import annotations

import time
import uuid

import jwt
import pytest

from app.config.settings import settings
from app.db.session import SessionLocal
from app.db.models.category import Category, CategoryType
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_ranking import PlaceRanking, TIER_SCORE_BANDS
from app.services.personal_ranking import ranking_service
from app.services.personal_ranking.ranking_service import RankingError


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def city(db):
    suffix = uuid.uuid4().hex[:8]
    c = City(slug=f"ranking-test-{suffix}", name=f"Ranking Test City {suffix}")
    db.add(c)
    db.commit()

    yield c

    db.query(PlaceRanking).filter(
        PlaceRanking.place_id.in_(db.query(Place.id).filter(Place.city_id == c.id))
    ).delete(synchronize_session=False)
    db.query(Place).filter(Place.city_id == c.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _make_places(db, city, n):
    places = []
    for i in range(n):
        p = Place(name=f"Ranking Test Place {i} {uuid.uuid4().hex[:6]}", city_id=city.id)
        db.add(p)
        places.append(p)
    db.commit()
    return places


def _seed_ranking(db, *, user_id, place_id, tier, score):
    r = PlaceRanking(user_id=user_id, place_id=place_id, tier=tier, rank_score=score)
    db.add(r)
    db.commit()
    return r


def _make_cuisine(db, name):
    slug = f"{name}-{uuid.uuid4().hex[:8]}"
    cat = Category(slug=slug, name=slug, type=CategoryType.cuisine)
    db.add(cat)
    db.commit()
    return cat


def _tag(db, place, *categories):
    place.categories = list(categories)
    db.add(place)
    db.commit()


# ---------------------------------------------------------------------------
# First ranking in an empty tier — no comparison needed.
# ---------------------------------------------------------------------------

def test_first_ranking_in_liked_tier_gets_band_midpoint(db, city):
    place, = _make_places(db, city, 1)
    result = ranking_service.start_ranking(
        db, user_id="alice", place_id=place.id, tier="liked",
    )
    assert result["status"] == "ranked"
    lo, hi = TIER_SCORE_BANDS["liked"]
    assert result["ranking"].rank_score == pytest.approx((lo + hi) / 2)


def test_first_ranking_in_fine_and_disliked_tiers(db, city):
    fine_place, disliked_place = _make_places(db, city, 2)

    fine_result = ranking_service.start_ranking(
        db, user_id="alice", place_id=fine_place.id, tier="fine",
    )
    disliked_result = ranking_service.start_ranking(
        db, user_id="alice", place_id=disliked_place.id, tier="disliked",
    )

    assert fine_result["ranking"].rank_score == pytest.approx(
        sum(TIER_SCORE_BANDS["fine"]) / 2
    )
    assert disliked_result["ranking"].rank_score == pytest.approx(
        sum(TIER_SCORE_BANDS["disliked"]) / 2
    )
    # Tier bands never overlap regardless of how comparisons land.
    assert disliked_result["ranking"].rank_score < fine_result["ranking"].rank_score


# ---------------------------------------------------------------------------
# Second+ ranking triggers the comparison flow.
# ---------------------------------------------------------------------------

def test_second_ranking_in_tier_returns_comparison(db, city):
    existing, new = _make_places(db, city, 2)
    _seed_ranking(db, user_id="alice", place_id=existing.id, tier="liked", score=8.0)

    result = ranking_service.start_ranking(
        db, user_id="alice", place_id=new.id, tier="liked",
    )
    assert result["status"] == "comparing"
    assert result["opponent_place_id"] == existing.id
    assert isinstance(result["comparison_token"], str)


# ---------------------------------------------------------------------------
# Binary search converges correctly to top / bottom / middle.
# ---------------------------------------------------------------------------

def test_new_place_winning_every_comparison_lands_at_the_top(db, city):
    a, b, c_, new = _make_places(db, city, 4)
    _seed_ranking(db, user_id="alice", place_id=a.id, tier="liked", score=7.0)
    _seed_ranking(db, user_id="alice", place_id=b.id, tier="liked", score=8.0)
    _seed_ranking(db, user_id="alice", place_id=c_.id, tier="liked", score=9.0)

    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")
    while result["status"] == "comparing":
        result = ranking_service.submit_comparison(
            db, token=result["comparison_token"], winner="new",
        )

    assert result["ranking"].rank_score > 9.0
    assert result["ranking"].rank_score <= TIER_SCORE_BANDS["liked"][1]


def test_new_place_losing_every_comparison_lands_at_the_bottom(db, city):
    a, b, c_, new = _make_places(db, city, 4)
    _seed_ranking(db, user_id="alice", place_id=a.id, tier="liked", score=7.0)
    _seed_ranking(db, user_id="alice", place_id=b.id, tier="liked", score=8.0)
    _seed_ranking(db, user_id="alice", place_id=c_.id, tier="liked", score=9.0)

    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")
    while result["status"] == "comparing":
        result = ranking_service.submit_comparison(
            db, token=result["comparison_token"], winner="opponent",
        )

    assert result["ranking"].rank_score < 7.0
    assert result["ranking"].rank_score >= TIER_SCORE_BANDS["liked"][0]


def test_split_decision_lands_new_place_in_the_middle(db, city):
    a, b, c_, new = _make_places(db, city, 4)
    _seed_ranking(db, user_id="alice", place_id=a.id, tier="liked", score=7.0)
    _seed_ranking(db, user_id="alice", place_id=b.id, tier="liked", score=8.0)
    _seed_ranking(db, user_id="alice", place_id=c_.id, tier="liked", score=9.0)

    # First comparison is against the score=8.0 place (index 1 of 3).
    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")
    assert result["opponent_place_id"] == b.id

    # new loses to 8.0 (new < 8.0) -> search left half -> next opponent is 7.0
    result = ranking_service.submit_comparison(
        db, token=result["comparison_token"], winner="opponent",
    )
    assert result["opponent_place_id"] == a.id

    # new beats 7.0 (new > 7.0) -> converged strictly between 7.0 and 8.0
    result = ranking_service.submit_comparison(
        db, token=result["comparison_token"], winner="new",
    )
    assert result["status"] == "ranked"
    assert 7.0 < result["ranking"].rank_score < 8.0
    assert result["ranking"].rank_score == pytest.approx(7.5)


# ---------------------------------------------------------------------------
# Comparisons are scoped to same-cuisine places — Beli's most-cited flaw
# (forcing a bagel shop against a steakhouse) is the thing this avoids.
# ---------------------------------------------------------------------------

def test_new_place_never_compared_against_a_different_cuisine(db, city):
    bbq = _make_cuisine(db, "bbq")
    ethiopian = _make_cuisine(db, "ethiopian")
    existing_bbq, existing_eth, new_bbq = _make_places(db, city, 3)
    _tag(db, existing_bbq, bbq)
    _tag(db, existing_eth, ethiopian)
    _tag(db, new_bbq, bbq)

    _seed_ranking(db, user_id="alice", place_id=existing_bbq.id, tier="liked", score=8.0)
    _seed_ranking(db, user_id="alice", place_id=existing_eth.id, tier="liked", score=9.5)

    result = ranking_service.start_ranking(db, user_id="alice", place_id=new_bbq.id, tier="liked")
    # Only one same-cuisine (BBQ) place exists — the Ethiopian one, despite
    # outscoring it, must never be offered as the opponent.
    assert result["opponent_place_id"] == existing_bbq.id


def test_first_place_of_a_new_cuisine_skips_comparison_entirely(db, city):
    bbq = _make_cuisine(db, "bbq")
    ethiopian = _make_cuisine(db, "ethiopian")
    existing_bbq, new_eth = _make_places(db, city, 2)
    _tag(db, existing_bbq, bbq)
    _tag(db, new_eth, ethiopian)

    _seed_ranking(db, user_id="alice", place_id=existing_bbq.id, tier="liked", score=8.0)

    # Tier is non-empty (has a BBQ place), but no Ethiopian place exists yet
    # in it — should place immediately, same as an empty tier, not force a
    # cross-cuisine comparison against the BBQ place.
    result = ranking_service.start_ranking(db, user_id="alice", place_id=new_eth.id, tier="liked")
    assert result["status"] == "ranked"
    lo, hi = TIER_SCORE_BANDS["liked"]
    assert result["ranking"].rank_score == pytest.approx((lo + hi) / 2)


def test_uncategorized_place_falls_back_to_comparing_against_the_whole_tier(db, city):
    # No categories tagged at all (the common case for older/uncategorized
    # data) — must not silently stop comparing just because there's no
    # cuisine info to scope by.
    existing, new = _make_places(db, city, 2)
    _seed_ranking(db, user_id="alice", place_id=existing.id, tier="liked", score=8.0)

    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")
    assert result["status"] == "comparing"
    assert result["opponent_place_id"] == existing.id


# ---------------------------------------------------------------------------
# "skip" — the escape hatch for a comparison the user has no opinion on.
# ---------------------------------------------------------------------------

def test_skip_converges_immediately_next_to_the_opponent(db, city):
    a, b, new = _make_places(db, city, 3)
    _seed_ranking(db, user_id="alice", place_id=a.id, tier="liked", score=7.0)
    _seed_ranking(db, user_id="alice", place_id=b.id, tier="liked", score=8.0)

    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")
    assert result["status"] == "comparing"

    result = ranking_service.submit_comparison(
        db, token=result["comparison_token"], winner="skip",
    )
    assert result["status"] == "ranked"
    # Landed adjacent to whichever place it was asked to skip on, not
    # pushed all the way to the top or bottom of the tier.
    assert TIER_SCORE_BANDS["liked"][0] < result["ranking"].rank_score < TIER_SCORE_BANDS["liked"][1]


def test_skip_is_a_valid_winner_value(db, city):
    existing, new = _make_places(db, city, 2)
    _seed_ranking(db, user_id="alice", place_id=existing.id, tier="liked", score=8.0)
    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")

    # Must not raise — "skip" is accepted alongside "new"/"opponent".
    result = ranking_service.submit_comparison(
        db, token=result["comparison_token"], winner="skip",
    )
    assert result["status"] == "ranked"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_invalid_tier_raises(db, city):
    place, = _make_places(db, city, 1)
    with pytest.raises(RankingError, match="tier"):
        ranking_service.start_ranking(db, user_id="alice", place_id=place.id, tier="amazing")


def test_nonexistent_place_raises(db):
    with pytest.raises(RankingError, match="place not found"):
        ranking_service.start_ranking(db, user_id="alice", place_id="does-not-exist", tier="liked")


def test_ranking_the_same_place_twice_raises(db, city):
    place, = _make_places(db, city, 1)
    ranking_service.start_ranking(db, user_id="alice", place_id=place.id, tier="liked")
    with pytest.raises(RankingError, match="already ranked"):
        ranking_service.start_ranking(db, user_id="alice", place_id=place.id, tier="fine")


# ---------------------------------------------------------------------------
# Comparison token integrity
# ---------------------------------------------------------------------------

def test_comparison_token_rejects_mismatched_user(db, city):
    existing, new = _make_places(db, city, 2)
    _seed_ranking(db, user_id="alice", place_id=existing.id, tier="liked", score=8.0)

    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")
    with pytest.raises(RankingError, match="different user"):
        ranking_service.submit_comparison(
            db, token=result["comparison_token"], winner="new", expected_user_id="mallory",
        )


def test_tampered_comparison_token_rejected(db, city):
    existing, new = _make_places(db, city, 2)
    _seed_ranking(db, user_id="alice", place_id=existing.id, tier="liked", score=8.0)

    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")
    tampered = result["comparison_token"][:-2] + "xx"
    with pytest.raises(RankingError, match="invalid or expired"):
        ranking_service.submit_comparison(db, token=tampered, winner="new")


def test_expired_comparison_token_rejected(db, city):
    existing, new = _make_places(db, city, 2)
    _seed_ranking(db, user_id="alice", place_id=existing.id, tier="liked", score=8.0)

    expired_payload = {
        "user_id": "alice", "place_id": new.id, "tier": "liked",
        "lo": 0, "hi": 1, "visited_at": None, "note": None, "tags": None,
        "exp": int(time.time()) - 10,
    }
    expired_token = jwt.encode(expired_payload, settings.secret_key, algorithm="HS256")

    with pytest.raises(RankingError, match="invalid or expired"):
        ranking_service.submit_comparison(db, token=expired_token, winner="new")


def test_invalid_winner_value_raises(db, city):
    existing, new = _make_places(db, city, 2)
    _seed_ranking(db, user_id="alice", place_id=existing.id, tier="liked", score=8.0)
    result = ranking_service.start_ranking(db, user_id="alice", place_id=new.id, tier="liked")

    with pytest.raises(RankingError, match="winner"):
        ranking_service.submit_comparison(
            db, token=result["comparison_token"], winner="tie",
        )


# ---------------------------------------------------------------------------
# CRUD around an existing ranking
# ---------------------------------------------------------------------------

def test_delete_ranking_allows_re_ranking(db, city):
    place, = _make_places(db, city, 1)
    ranking_service.start_ranking(db, user_id="alice", place_id=place.id, tier="liked")

    assert ranking_service.delete_ranking(db, user_id="alice", place_id=place.id) is True
    assert ranking_service.delete_ranking(db, user_id="alice", place_id=place.id) is False

    # Now re-rankable.
    result = ranking_service.start_ranking(db, user_id="alice", place_id=place.id, tier="fine")
    assert result["status"] == "ranked"


def test_update_ranking_metadata_does_not_touch_score(db, city):
    place, = _make_places(db, city, 1)
    result = ranking_service.start_ranking(db, user_id="alice", place_id=place.id, tier="liked")
    original_score = result["ranking"].rank_score

    updated = ranking_service.update_ranking_metadata(
        db, user_id="alice", place_id=place.id, note="great tacos", tags=["date_night"],
    )
    assert updated.note == "great tacos"
    assert updated.tags == ["date_night"]
    assert updated.rank_score == pytest.approx(original_score)


def test_update_missing_ranking_raises(db, city):
    place, = _make_places(db, city, 1)
    with pytest.raises(RankingError, match="not found"):
        ranking_service.update_ranking_metadata(db, user_id="alice", place_id=place.id, note="x")


def test_list_user_rankings_ordered_highest_first(db, city):
    a, b, c_ = _make_places(db, city, 3)
    _seed_ranking(db, user_id="alice", place_id=a.id, tier="liked", score=7.0)
    _seed_ranking(db, user_id="alice", place_id=b.id, tier="liked", score=9.0)
    _seed_ranking(db, user_id="alice", place_id=c_.id, tier="fine", score=5.0)

    rankings = ranking_service.list_user_rankings(db, "alice")
    scores = [r.rank_score for r in rankings]
    assert scores == sorted(scores, reverse=True)
