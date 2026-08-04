"""
Coverage for app.services.upload.dedup.is_duplicate_image.

Before this fix, the comparison was scoped to `place_id`, so the actual
spam pattern platforms like Yelp specifically call out — one stock photo
seeded across dozens of different restaurants — was invisible to it:
every upload was only ever compared against that one place's own photos.
"""
from __future__ import annotations

import random
import uuid

import pytest
from PIL import Image, ImageDraw

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.services.upload.dedup import compute_phash, is_duplicate_image


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def two_places(db):
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"dedup-test-{suffix}", name=f"Dedup Test City {suffix}")
    db.add(city)
    db.flush()

    a = Place(name=f"Dedup Place A {suffix}", city_id=city.id)
    b = Place(name=f"Dedup Place B {suffix}", city_id=city.id)
    db.add(a)
    db.add(b)
    db.commit()

    yield a, b

    db.query(PlaceImage).filter(PlaceImage.place_id.in_([a.id, b.id])).delete(
        synchronize_session=False
    )
    db.query(Place).filter(Place.id.in_([a.id, b.id])).delete(synchronize_session=False)
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def _seed_image(db, place, phash):
    row = PlaceImage(place_id=place.id, url="https://example.com/x.jpg", phash=phash)
    db.add(row)
    db.commit()
    return row


def _patterned_image(seed: int) -> Image.Image:
    """
    A flat-color image has zero frequency content, so phash collapses
    every solid color to the SAME hash regardless of RGB value — verified
    directly (two different solid colors produced Hamming distance 0).
    Real structure is required to get genuinely distinguishing hashes,
    same lesson as the quality_analyzer tests.
    """
    img = Image.new("RGB", (256, 256), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    rng = random.Random(seed)
    for _ in range(40):
        x, y = rng.randint(0, 200), rng.randint(0, 200)
        draw.rectangle(
            [x, y, x + rng.randint(10, 50), y + rng.randint(10, 50)],
            fill=(rng.randint(0, 255), rng.randint(0, 255), rng.randint(0, 255)),
        )
    return img


def _hash_of(seed: int) -> str:
    return compute_phash(_patterned_image(seed))


def test_no_existing_images_anywhere_is_not_a_duplicate(db, two_places):
    a, _b = two_places
    assert is_duplicate_image(db, place_id=a.id, new_phash=_hash_of(1)) is False


def test_exact_reuse_on_a_different_place_is_caught(db, two_places):
    """The actual spam pattern: the same stock photo uploaded to a
    different restaurant than the one it already exists on."""
    a, b = two_places
    phash = _hash_of(2)
    _seed_image(db, a, phash)

    assert is_duplicate_image(db, place_id=b.id, new_phash=phash) is True


def test_exact_reuse_on_the_same_place_is_still_caught(db, two_places):
    a, _b = two_places
    phash = _hash_of(3)
    _seed_image(db, a, phash)

    assert is_duplicate_image(db, place_id=a.id, new_phash=phash) is True


def test_a_genuinely_different_photo_on_another_place_is_not_flagged(db, two_places):
    a, b = two_places
    _seed_image(db, a, _hash_of(4))

    distinct = _hash_of(5)
    assert is_duplicate_image(db, place_id=b.id, new_phash=distinct) is False


def test_blank_phash_is_never_a_duplicate(db, two_places):
    a, _b = two_places
    assert is_duplicate_image(db, place_id=a.id, new_phash="") is False


def test_malformed_existing_phash_does_not_crash_the_scan(db, two_places):
    a, b = two_places
    corrupt = PlaceImage(place_id=a.id, url="https://example.com/y.jpg", phash="not-a-real-hash")
    db.add(corrupt)
    db.commit()

    # Must not raise despite the corrupt row sitting in the global scan.
    assert is_duplicate_image(db, place_id=b.id, new_phash=_hash_of(6)) is False
