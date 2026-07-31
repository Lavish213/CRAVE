# tests/test_truth_resolver_v2.py
"""
Tests for app.services.truth.truth_resolver_v2.resolve_place_truths_v2.

This file was previously 0 bytes — pytest collected nothing from it, so
"143 passed, 0 skipped" never reflected whether the truth resolver actually
worked. The resolver is load-bearing: every promotion (see
test_promotion_pipeline_v2.py) calls it to turn raw PlaceClaim rows into
canonical PlaceTruth rows, and it's the thing that decides which of several
conflicting claims about a place (different names, addresses, prices from
different sources) wins.

Covers: empty input, single-claim resolution, weighted winner selection,
the verified-source boost, the user-submitted penalty, freshness decay,
deterministic tie-breaking, and idempotent upsert (no duplicate PlaceTruth
rows on repeated runs).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.services.truth.truth_resolver_v2 import resolve_place_truths_v2


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def place(db):
    """A throwaway City + Place, cleaned up after the test."""
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"truth-test-{suffix}", name=f"Truth Test City {suffix}")
    db.add(city)
    db.flush()

    p = Place(name=f"Truth Test Place {suffix}", city_id=city.id)
    db.add(p)
    db.commit()

    yield p

    db.query(PlaceTruth).filter(PlaceTruth.place_id == p.id).delete()
    db.query(PlaceClaim).filter(PlaceClaim.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def _add_claim(
    db,
    place_id: str,
    *,
    field: str = "name",
    value_text: str | None = None,
    value_number: float | None = None,
    confidence: float = 0.5,
    weight: float = 1.0,
    source: str = "test",
    claim_key: str | None = None,
    is_verified_source: bool = False,
    is_user_submitted: bool = False,
    created_at: datetime | None = None,
) -> PlaceClaim:
    claim = PlaceClaim(
        place_id=place_id,
        field=field,
        claim_key=claim_key or uuid.uuid4().hex[:16],
        value_text=value_text,
        value_number=value_number,
        confidence=confidence,
        weight=weight,
        source=source,
        is_verified_source=is_verified_source,
        is_user_submitted=is_user_submitted,
    )
    if created_at is not None:
        claim.created_at = created_at
    db.add(claim)
    db.flush()
    return claim


# ---------------------------------------------------------------------------
# Empty / trivial input
# ---------------------------------------------------------------------------

def test_no_place_id_returns_empty_list(db):
    assert resolve_place_truths_v2(db=db, place_id="") == []
    assert resolve_place_truths_v2(db=db, place_id=None) == []


def test_place_with_no_claims_returns_empty_list(db, place):
    assert resolve_place_truths_v2(db=db, place_id=place.id) == []


def test_claim_with_blank_value_is_ignored(db, place):
    """A claim whose normalized value is empty/None contributes nothing —
    resolver should skip it rather than crash or pick an empty winner."""
    _add_claim(db, place.id, field="phone", value_text="   ")
    db.commit()
    assert resolve_place_truths_v2(db=db, place_id=place.id) == []


# ---------------------------------------------------------------------------
# Basic resolution
# ---------------------------------------------------------------------------

def test_single_claim_becomes_the_truth(db, place):
    _add_claim(db, place.id, field="phone", value_text="555-0100", confidence=0.8)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert len(truths) == 1
    assert truths[0].truth_type == "phone"
    assert truths[0].truth_value == "555-0100"
    # Sole claim, normalized_score = 1.0 of the total → full confidence.
    assert truths[0].confidence == pytest.approx(1.0)
    assert truths[0].resolver_version == "v2"


def test_numeric_claim_value_is_stringified(db, place):
    _add_claim(db, place.id, field="price_tier", value_number=2, confidence=0.9)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert len(truths) == 1
    assert truths[0].truth_value == "2.0"


def test_multiple_fields_each_get_their_own_truth(db, place):
    _add_claim(db, place.id, field="name", value_text="Horn BBQ", confidence=0.9)
    _add_claim(db, place.id, field="phone", value_text="555-0100", confidence=0.9)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    by_type = {t.truth_type: t.truth_value for t in truths}
    assert by_type == {"name": "Horn BBQ", "phone": "555-0100"}


# ---------------------------------------------------------------------------
# Weighted winner selection
# ---------------------------------------------------------------------------

def test_higher_confidence_claim_wins(db, place):
    _add_claim(db, place.id, field="name", value_text="Old Name", confidence=0.3)
    _add_claim(db, place.id, field="name", value_text="New Name", confidence=0.9)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert len(truths) == 1
    assert truths[0].truth_value == "New Name"


def test_higher_weight_can_overcome_lower_confidence(db, place):
    # weight * confidence: 0.9 * 0.4 = 0.36  vs  0.5 * 0.5 = 0.25
    _add_claim(db, place.id, field="name", value_text="Heavy Claim",
               confidence=0.4, weight=0.9)
    _add_claim(db, place.id, field="name", value_text="Light Claim",
               confidence=0.5, weight=0.5)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert truths[0].truth_value == "Heavy Claim"


def test_verified_source_boost_can_flip_the_winner(db, place):
    # Equal confidence/weight, but the verified claim gets a 1.15x boost —
    # enough to beat an otherwise-equal unverified claim.
    _add_claim(db, place.id, field="name", value_text="Unverified Name",
               confidence=0.6, weight=1.0, is_verified_source=False)
    _add_claim(db, place.id, field="name", value_text="Verified Name",
               confidence=0.6, weight=1.0, is_verified_source=True)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert truths[0].truth_value == "Verified Name"


def test_user_submitted_unverified_claim_is_penalized(db, place):
    # Both start at confidence=0.55, weight=1.0. The user-submitted claim
    # gets *0.9, the plain (non-user, non-verified) claim doesn't — so the
    # plain claim should win despite identical inputs otherwise.
    _add_claim(db, place.id, field="name", value_text="User Submitted",
               confidence=0.55, weight=1.0, is_user_submitted=True)
    _add_claim(db, place.id, field="name", value_text="System Claim",
               confidence=0.55, weight=1.0, is_user_submitted=False)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert truths[0].truth_value == "System Claim"


def test_verified_user_submitted_claim_is_not_penalized(db, place):
    # is_user_submitted + is_verified_source together → only the verified
    # boost applies, the 0.9 penalty is explicitly gated on "not verified".
    _add_claim(db, place.id, field="name", value_text="Verified User Claim",
               confidence=0.6, weight=1.0,
               is_user_submitted=True, is_verified_source=True)
    _add_claim(db, place.id, field="name", value_text="Plain Claim",
               confidence=0.6, weight=1.0)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert truths[0].truth_value == "Verified User Claim"


# ---------------------------------------------------------------------------
# Freshness decay
# ---------------------------------------------------------------------------

def test_fresher_claim_wins_when_otherwise_equal(db, place):
    now = datetime.now(timezone.utc)
    old = now - timedelta(days=120)  # freshness 0.4
    recent = now - timedelta(days=1)  # freshness 1.0

    _add_claim(db, place.id, field="name", value_text="Stale Name",
               confidence=0.7, weight=1.0, created_at=old)
    _add_claim(db, place.id, field="name", value_text="Fresh Name",
               confidence=0.7, weight=1.0, created_at=recent)
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert truths[0].truth_value == "Fresh Name"


# ---------------------------------------------------------------------------
# Deterministic tie-break
# ---------------------------------------------------------------------------

def test_exact_ties_break_alphabetically(db, place):
    """Two claims with identical scores must resolve deterministically
    (same winner every run) rather than depend on dict/query ordering."""
    _add_claim(db, place.id, field="name", value_text="Zebra Diner", confidence=0.5)
    _add_claim(db, place.id, field="name", value_text="Apple Diner", confidence=0.5)
    db.commit()

    first = resolve_place_truths_v2(db=db, place_id=place.id)[0].truth_value
    db.rollback()

    # Re-run against the same claims — must be stable, not just "a valid pick".
    second = resolve_place_truths_v2(db=db, place_id=place.id)[0].truth_value

    assert first == second == "Apple Diner"  # alphabetically first on a tie


# ---------------------------------------------------------------------------
# Idempotent upsert
# ---------------------------------------------------------------------------

def test_resolving_twice_updates_in_place_not_duplicates(db, place):
    _add_claim(db, place.id, field="name", value_text="First Pass", confidence=0.8)
    db.commit()

    resolve_place_truths_v2(db=db, place_id=place.id)
    db.commit()

    first_count = (
        db.query(PlaceTruth)
        .filter(PlaceTruth.place_id == place.id, PlaceTruth.truth_type == "name")
        .count()
    )
    assert first_count == 1

    # A new, stronger claim arrives; re-resolving should update the existing
    # row (same unique place_id+truth_type), not insert a second one.
    _add_claim(db, place.id, field="name", value_text="Second Pass", confidence=0.95)
    db.commit()

    resolve_place_truths_v2(db=db, place_id=place.id)
    db.commit()

    rows = (
        db.query(PlaceTruth)
        .filter(PlaceTruth.place_id == place.id, PlaceTruth.truth_type == "name")
        .all()
    )
    assert len(rows) == 1
    assert rows[0].truth_value == "Second Pass"


def test_resolved_from_is_valid_json_and_bounded(db, place):
    import json

    _add_claim(db, place.id, field="name", value_text="Bounded Name",
                confidence=0.7, source="unit-test")
    db.commit()

    truths = resolve_place_truths_v2(db=db, place_id=place.id)

    assert truths[0].resolved_from is not None
    assert len(truths[0].resolved_from) <= 512
    parsed = json.loads(truths[0].resolved_from)
    assert isinstance(parsed, list)
    assert parsed[0]["source"] == "unit-test"
