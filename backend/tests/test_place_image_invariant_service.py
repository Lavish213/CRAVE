"""
Coverage for PlaceImageInvariantService — the hard-invariant enforcer for
place_images (only one primary, hidden can't be primary, etc).

Found via live production diagnosis (not a hypothetical): a place had two
is_primary=True rows — an old Google Places photo reference (confidence
0.8) and a newer, working, durably-hosted photo scraped from the
restaurant's own site (confidence 0.556). repair()'s duplicate-primary
resolution picked purely by confidence, so it kept the *dead* Google
reference as primary and demoted the working photo — actively breaking a
place that was already displaying correctly. Google's photo references
are session-scoped and can go dead at any time regardless of how
confident the extractor was when it found them; confidence measures
extraction quality, not whether the URL still resolves. These tests lock
in the fix: a durable (non-ephemeral) URL always wins over a raw Google
reference, confidence only breaks ties within the same durability class.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import (
    PlaceImage,
    VISIBILITY_GALLERY_ONLY,
    VISIBILITY_HIDDEN,
)
from app.services.images.place_image_invariant_service import (
    PlaceImageInvariantService,
    _is_ephemeral_google_ref,
)

GOOGLE_REF_URL = "https://places.googleapis.com/v1/places/abc/photos/xyz"
BARE_GOOGLE_REF = "places/abc/photos/xyz"
DURABLE_URL = "https://pub-abc123.r2.dev/google-photos/place/img.jpg"


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def place(db):
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"invariant-{suffix}", name=f"Invariant Test City {suffix}")
    db.add(city)
    db.flush()
    p = Place(name=f"Invariant Place {suffix}", city_id=city.id, is_active=True)
    db.add(p)
    db.commit()

    yield p

    db.query(PlaceImage).filter(PlaceImage.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def _image(place_id, **overrides):
    defaults = dict(
        place_id=place_id,
        url="https://example.test/img.jpg",
        is_primary=False,
        visibility_status=VISIBILITY_GALLERY_ONLY,
        confidence=0.5,
    )
    defaults.update(overrides)
    return PlaceImage(**defaults)


# ---------------------------------------------------------------------------
# _is_ephemeral_google_ref
# ---------------------------------------------------------------------------

def test_is_ephemeral_google_ref_true_for_full_googleapis_url():
    assert _is_ephemeral_google_ref(GOOGLE_REF_URL) is True


def test_is_ephemeral_google_ref_true_for_bare_resource_name():
    assert _is_ephemeral_google_ref(BARE_GOOGLE_REF) is True


def test_is_ephemeral_google_ref_false_for_durable_url():
    assert _is_ephemeral_google_ref(DURABLE_URL) is False


def test_is_ephemeral_google_ref_false_for_none():
    assert _is_ephemeral_google_ref(None) is False


# ---------------------------------------------------------------------------
# Duplicate primary — the actual production bug
# ---------------------------------------------------------------------------

def test_duplicate_primary_prefers_durable_url_over_higher_confidence_google_ref(db, place):
    """The exact production scenario: a dead-prone Google ref with higher
    confidence must lose to a working durable photo with lower
    confidence."""
    google = _image(
        place.id, url=GOOGLE_REF_URL, is_primary=True,
        visibility_status="candidate_primary", confidence=0.8,
    )
    durable = _image(
        place.id, url=DURABLE_URL, is_primary=True,
        visibility_status=VISIBILITY_GALLERY_ONLY, confidence=0.556,
    )
    db.add_all([google, durable])
    db.commit()

    result = PlaceImageInvariantService().repair(db=db, place_id=place.id)
    db.commit()

    assert result["duplicate_primary_fixed"] is True
    db.refresh(google)
    db.refresh(durable)
    assert durable.is_primary is True
    assert google.is_primary is False


def test_duplicate_primary_falls_back_to_confidence_within_same_durability_class(db, place):
    """Two durable URLs (or two Google refs) — confidence still decides,
    since there's no durability signal to prefer between them."""
    low = _image(place.id, url=DURABLE_URL, is_primary=True, confidence=0.3)
    high = _image(
        place.id, url="https://pub-abc123.r2.dev/other.jpg",
        is_primary=True, confidence=0.9,
    )
    db.add_all([low, high])
    db.commit()

    PlaceImageInvariantService().repair(db=db, place_id=place.id)
    db.commit()

    db.refresh(low)
    db.refresh(high)
    assert high.is_primary is True
    assert low.is_primary is False


def test_duplicate_primary_ignores_a_hidden_candidate(db, place):
    hidden = _image(
        place.id, url=DURABLE_URL, is_primary=True,
        visibility_status=VISIBILITY_HIDDEN, confidence=0.99,
    )
    visible = _image(
        place.id, url=GOOGLE_REF_URL, is_primary=True,
        visibility_status=VISIBILITY_GALLERY_ONLY, confidence=0.1,
    )
    db.add_all([hidden, visible])
    db.commit()

    PlaceImageInvariantService().repair(db=db, place_id=place.id)
    db.commit()

    db.refresh(hidden)
    db.refresh(visible)
    assert visible.is_primary is True
    assert hidden.is_primary is False


def test_no_duplicate_is_a_no_op(db, place):
    only = _image(place.id, url=DURABLE_URL, is_primary=True)
    db.add(only)
    db.commit()

    result = PlaceImageInvariantService().repair(db=db, place_id=place.id)

    assert result["duplicate_primary_fixed"] is False
    db.refresh(only)
    assert only.is_primary is True


# ---------------------------------------------------------------------------
# Hidden primary — promotion also prefers durable URLs
# ---------------------------------------------------------------------------

def test_hidden_primary_promotes_durable_candidate_over_higher_confidence_google_ref(db, place):
    hidden_primary = _image(
        place.id, url="https://example.test/hidden.jpg",
        is_primary=True, visibility_status=VISIBILITY_HIDDEN, confidence=0.9,
    )
    google_candidate = _image(
        place.id, url=GOOGLE_REF_URL, is_primary=False,
        visibility_status=VISIBILITY_GALLERY_ONLY, confidence=0.8,
    )
    durable_candidate = _image(
        place.id, url=DURABLE_URL, is_primary=False,
        visibility_status=VISIBILITY_GALLERY_ONLY, confidence=0.4,
    )
    db.add_all([hidden_primary, google_candidate, durable_candidate])
    db.commit()

    result = PlaceImageInvariantService().repair(db=db, place_id=place.id)
    db.commit()

    assert result["hidden_primary_fixed"] is True
    db.refresh(hidden_primary)
    db.refresh(google_candidate)
    db.refresh(durable_candidate)
    assert hidden_primary.is_primary is False
    assert durable_candidate.is_primary is True
    assert google_candidate.is_primary is False
