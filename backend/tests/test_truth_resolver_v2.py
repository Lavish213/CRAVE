"""
Real coverage for app.services.truth.truth_resolver_v2.resolve_place_truths_v2
— this file was 0 bytes before this pass despite the resolver being the
core of the whole truth/promotion system (every promoted Place's canonical
field values come from here).

Exercises the resolver directly against PlaceClaim rows rather than going
through promotion, so the scoring rules (confidence * weight * freshness,
verified-source boost, unverified-user-submitted penalty) can be pinned
down precisely instead of only observed indirectly.
"""
from __future__ import annotations

import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.services.truth.truth_resolver_v2 import resolve_place_truths_v2


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def place(db) -> Place:
    city = City(
        id=str(uuid.uuid4()),
        name="Truth Resolver Test City",
        slug=f"truth-test-{uuid.uuid4().hex[:8]}",
        lat=37.8,
        lng=-122.27,
        is_active=True,
    )
    db.add(city)
    p = Place(
        id=str(uuid.uuid4()),
        name="Truth Resolver Test Place",
        city_id=city.id,
        lat=37.8,
        lng=-122.27,
        is_active=True,
    )
    db.add(p)
    db.commit()
    return p


def _add_claim(db, place, *, field, claim_key, value_text=None, value_number=None,
                confidence=0.5, weight=1.0, source="test", is_verified_source=False,
                is_user_submitted=False, created_at=None) -> PlaceClaim:
    claim = PlaceClaim(
        id=str(uuid.uuid4()),
        place_id=place.id,
        field=field,
        claim_key=claim_key,
        value_text=value_text,
        value_number=value_number,
        confidence=confidence,
        weight=weight,
        source=source,
        is_verified_source=is_verified_source,
        is_user_submitted=is_user_submitted,
        **({"created_at": created_at} if created_at is not None else {}),
    )
    db.add(claim)
    db.commit()
    return claim


def test_resolve_returns_empty_for_blank_place_id(db):
    assert resolve_place_truths_v2(db=db, place_id="") == []
    assert resolve_place_truths_v2(db=db, place_id=None) == []


def test_resolve_returns_empty_when_no_claims(db, place):
    assert resolve_place_truths_v2(db=db, place_id=place.id) == []


def test_resolve_picks_highest_scoring_claim_as_winner(db, place):
    _add_claim(
        db, place, field="cuisine", claim_key="weak",
        value_text="pizza", confidence=0.3, weight=1.0,
    )
    _add_claim(
        db, place, field="cuisine", claim_key="strong",
        value_text="italian", confidence=0.9, weight=1.0,
    )

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    cuisine = next(t for t in truths if t.truth_type == "cuisine")
    assert cuisine.truth_value == "italian"
    assert 0.0 <= cuisine.confidence <= 1.0


def test_verified_source_boost_can_overturn_a_close_contest(db, place):
    # Equal confidence/weight; only the verified-source multiplier (1.15x)
    # differs, so the verified claim must win.
    _add_claim(
        db, place, field="phone", claim_key="unverified",
        value_text="555-0100", confidence=0.6, weight=1.0,
        is_verified_source=False,
    )
    _add_claim(
        db, place, field="phone", claim_key="verified",
        value_text="555-0199", confidence=0.6, weight=1.0,
        is_verified_source=True,
    )

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    phone = next(t for t in truths if t.truth_type == "phone")
    assert phone.truth_value == "555-0199"


def test_unverified_user_submitted_claim_is_penalized(db, place):
    # Equal confidence/weight; the unverified user-submitted claim gets a
    # 0.9x penalty, so the plain (non-user-submitted) claim must win.
    _add_claim(
        db, place, field="hours", claim_key="user_submitted",
        value_text="24/7", confidence=0.6, weight=1.0,
        is_user_submitted=True, is_verified_source=False,
    )
    _add_claim(
        db, place, field="hours", claim_key="baseline",
        value_text="9am-5pm", confidence=0.6, weight=1.0,
        is_user_submitted=False, is_verified_source=False,
    )

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    hours = next(t for t in truths if t.truth_type == "hours")
    assert hours.truth_value == "9am-5pm"


def test_fresher_claim_wins_when_base_scores_are_tied(db, place):
    now = datetime.now(timezone.utc)
    _add_claim(
        db, place, field="price_hint", claim_key="old",
        value_text="cheap", confidence=0.6, weight=1.0,
        created_at=now - timedelta(days=120),
    )
    _add_claim(
        db, place, field="price_hint", claim_key="new",
        value_text="moderate", confidence=0.6, weight=1.0,
        created_at=now,
    )

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    price_hint = next(t for t in truths if t.truth_type == "price_hint")
    assert price_hint.truth_value == "moderate"


def test_resolve_is_idempotent_upsert_not_duplicate_rows(db, place):
    _add_claim(db, place, field="name", claim_key="a", value_text="First Name", confidence=0.9)

    resolve_place_truths_v2(db=db, place_id=place.id)
    resolve_place_truths_v2(db=db, place_id=place.id)

    rows = (
        db.query(PlaceTruth)
        .filter(PlaceTruth.place_id == place.id, PlaceTruth.truth_type == "name")
        .all()
    )
    assert len(rows) == 1


def test_resolve_updates_existing_truth_when_a_better_claim_arrives(db, place):
    _add_claim(db, place, field="name", claim_key="a", value_text="Old Name", confidence=0.5)
    resolve_place_truths_v2(db=db, place_id=place.id)

    truth = (
        db.query(PlaceTruth)
        .filter(PlaceTruth.place_id == place.id, PlaceTruth.truth_type == "name")
        .one()
    )
    # _claim_value() only strips PlaceClaim.value_text — it does not
    # lowercase (that normalization happens in claim_normalizer_v2, one
    # layer up, which this test deliberately bypasses to isolate the
    # resolver itself).
    assert truth.truth_value == "Old Name"

    _add_claim(db, place, field="name", claim_key="b", value_text="New Name", confidence=0.95)
    resolve_place_truths_v2(db=db, place_id=place.id)

    db.refresh(truth)
    assert truth.truth_value == "New Name"


def test_resolve_handles_numeric_claim_values(db, place):
    _add_claim(db, place, field="lat", claim_key="a", value_number=37.8044, confidence=0.9)

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    lat_truth = next(t for t in truths if t.truth_type == "lat")
    assert lat_truth.truth_value == str(float(37.8044))
