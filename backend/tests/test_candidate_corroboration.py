"""
Coverage for the corroboration-accumulation fix in
app.services.discovery.candidate_store_v2.upsert_discovery_candidate_v2.

Before this fix, merging a repeat DiscoveryCandidate upsert always took
max(existing.confidence_score, new confidence_score) — never summed. Every
user-facing "I found a new place" signal is deliberately seeded well below
MIN_CONFIDENCE_THRESHOLD (0.72) on its own:

    GPS confirmation (nearby.py)            0.35
    unmatched social share (share_parser)   0.30
    hitlist suggestion (suggest_intake)     0.40
    hitlist save (save_intake)              0.45

Each of those modules' own comments/docstrings claim corroboration by a
second independent signal is what's supposed to push a candidate over the
threshold — but under max(), the ceiling across *any* combination of them
was 0.45 (the highest single one), forever short of 0.72. No amount of
real-world corroboration could ever promote a user-discovered place on its
own; only an automated source (OSM ~0.6, Google Places, health dept >=0.75)
scanning the same spot could.

The fix: a `contributor_key` identifies who/what is vouching (e.g.
"user_gps:<user_id>"). A genuinely new key accumulates confidence_score
instead of taking the max; the same contributor re-submitting doesn't let
them inflate it solo. Callers that never pass a contributor_key (automated
ingestion) are untouched — max() is correct there, since a re-scan by the
same source isn't new evidence.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.discovery.candidate_store_v2 import upsert_discovery_candidate_v2
from app.services.discovery.promotion_orchestrator_v2 import MIN_CONFIDENCE_THRESHOLD


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
    c = City(slug=f"corrob-test-{suffix}", name=f"Corroboration Test City {suffix}")
    db.add(c)
    db.commit()

    yield c

    db.query(DiscoveryCandidate).filter(DiscoveryCandidate.city_id == c.id).delete()
    db.query(City).filter(City.id == c.id).delete()
    db.commit()


def _upsert(db, city, **kwargs):
    defaults = dict(name="Test Spot", city_id=city.id)
    defaults.update(kwargs)
    candidate = upsert_discovery_candidate_v2(db=db, **defaults)
    db.commit()
    return candidate


# ---------------------------------------------------------------------------
# The bug, pinned: without a contributor_key, repeat upserts still just
# take the max (unchanged behavior for automated/authoritative sources).
# ---------------------------------------------------------------------------

def test_without_contributor_key_merge_is_still_max(db, city):
    _upsert(db, city, confidence_score=0.6, source="osm")
    second = _upsert(db, city, confidence_score=0.4, source="osm")

    assert second.confidence_score == pytest.approx(0.6)

    third = _upsert(db, city, confidence_score=0.65, source="osm")
    assert third.confidence_score == pytest.approx(0.65)


# ---------------------------------------------------------------------------
# The fix: distinct contributors accumulate.
# ---------------------------------------------------------------------------

def test_two_distinct_contributors_accumulate_past_max_of_either(db, city):
    _upsert(db, city, confidence_score=0.35, contributor_key="user_gps:alice")
    second = _upsert(db, city, confidence_score=0.4, contributor_key="user_hitlist_suggestion:bob")

    # 0.35 + 0.4 = 0.75 -- strictly more than max(0.35, 0.4) = 0.4, and
    # actually crosses the real promotion threshold.
    assert second.confidence_score == pytest.approx(0.75)
    assert second.confidence_score >= MIN_CONFIDENCE_THRESHOLD


def test_real_world_corroboration_combo_crosses_promotion_threshold(db, city):
    """Reproduces the exact bug: a GPS confirmation (0.35) plus a hitlist
    save (0.45) from two different people -- documented in nearby.py's own
    module docstring as exactly the scenario corroboration should handle --
    used to cap out at max(0.35, 0.45) = 0.45 forever. It must now promote."""
    _upsert(db, city, confidence_score=0.35, contributor_key="user_gps:alice")
    result = _upsert(db, city, confidence_score=0.45, contributor_key="user_hitlist_save:carol")

    assert result.confidence_score == pytest.approx(0.8)
    assert result.confidence_score >= MIN_CONFIDENCE_THRESHOLD


def test_same_contributor_resubmitting_does_not_accumulate_twice(db, city):
    """One person can't single-handedly inflate confidence by repeatedly
    confirming/sharing/suggesting the same spot."""
    _upsert(db, city, confidence_score=0.35, contributor_key="user_gps:alice")
    second = _upsert(db, city, confidence_score=0.35, contributor_key="user_gps:alice")
    third = _upsert(db, city, confidence_score=0.35, contributor_key="user_gps:alice")

    assert second.confidence_score == pytest.approx(0.35)
    assert third.confidence_score == pytest.approx(0.35)


def test_confidence_score_is_clamped_at_one(db, city):
    _upsert(db, city, confidence_score=0.6, contributor_key="user_gps:alice")
    _upsert(db, city, confidence_score=0.6, contributor_key="user_gps:bob")
    result = _upsert(db, city, confidence_score=0.6, contributor_key="user_gps:carol")

    assert result.confidence_score == pytest.approx(1.0)


def test_corroboration_keys_are_recorded(db, city):
    _upsert(db, city, confidence_score=0.35, contributor_key="user_gps:alice")
    result = _upsert(db, city, confidence_score=0.4, contributor_key="user_hitlist_suggestion:bob")

    assert result.corroboration_keys == ["user_gps:alice", "user_hitlist_suggestion:bob"]


def test_new_candidate_seeds_corroboration_keys_from_first_contributor(db, city):
    result = _upsert(db, city, confidence_score=0.35, contributor_key="user_gps:alice")
    assert result.corroboration_keys == ["user_gps:alice"]


def test_no_contributor_key_leaves_corroboration_keys_empty(db, city):
    result = _upsert(db, city, confidence_score=0.6, source="osm")
    assert not result.corroboration_keys
