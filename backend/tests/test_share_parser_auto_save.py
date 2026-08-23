"""
Coverage for share_parser_worker's auto-save behavior: a matched share now
also saves the place to the submitter's personal list (the same
HitlistSave row a manual POST /saves creates), not just marking the
CraveItem 'matched'. Before this, matching a share to a real place did
nothing for the person who shared it beyond a status change on their
pending item -- they'd have to separately find and save the place
themselves, unlike the "share it and it's on your map" behavior this is
meant to match.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.db.models.crave_item import CraveItem
from app.db.models.hitlist_save import HitlistSave
from app.workers.share_parser_worker import _process_item


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_city(db) -> City:
    city = City(
        id=str(uuid.uuid4()),
        name="Share Auto-Save Test City",
        slug=f"share-auto-save-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    return city


def _make_place(db, city: City) -> Place:
    place = Place(name="Auto Save Test Place", city_id=city.id, lat=37.8, lng=-122.27)
    db.add(place)
    db.commit()
    return place


def _make_item(db, **overrides) -> CraveItem:
    # A unique submitted_by per call (rather than a fixed literal) keeps
    # each test's HitlistSave assertions scoped to its own data, since
    # these tests share the same on-disk test DB with no per-test
    # transaction rollback.
    item = CraveItem(
        url=f"https://example.com/{uuid.uuid4().hex}",
        source_type="tiktok",
        submitted_by=f"user-{uuid.uuid4().hex[:12]}",
    )
    for key, value in overrides.items():
        setattr(item, key, value)
    db.add(item)
    db.commit()
    return item


def test_matched_share_auto_saves_place_for_submitter(db):
    city = _make_city(db)
    place = _make_place(db, city)
    item = _make_item(db)

    with patch(
        "app.workers.share_parser_worker.get_oembed_data",
        return_value={"title": place.name},
    ), patch(
        "app.workers.share_parser_worker._find_best_place_match",
        return_value=(place.id, 0.95),
    ):
        _process_item(db, item)

    db.refresh(item)
    assert item.status == "matched"

    save = (
        db.query(HitlistSave)
        .filter(HitlistSave.user_id == item.submitted_by, HitlistSave.place_id == place.id)
        .one_or_none()
    )
    assert save is not None
    assert save.dedup_key == f"save:{item.submitted_by}:{place.id}"
    assert save.resolution_status == "resolved"


def test_matched_share_does_not_duplicate_an_existing_save(db):
    city = _make_city(db)
    place = _make_place(db, city)
    item = _make_item(db)

    db.add(HitlistSave(
        user_id=item.submitted_by,
        place_name=place.name,
        place_id=place.id,
        resolution_status="resolved",
        dedup_key=f"save:{item.submitted_by}:{place.id}",
    ))
    db.commit()

    with patch(
        "app.workers.share_parser_worker.get_oembed_data",
        return_value={"title": place.name},
    ), patch(
        "app.workers.share_parser_worker._find_best_place_match",
        return_value=(place.id, 0.95),
    ):
        _process_item(db, item)

    count = (
        db.query(HitlistSave)
        .filter(HitlistSave.user_id == item.submitted_by, HitlistSave.place_id == place.id)
        .count()
    )
    assert count == 1


def test_unmatched_share_does_not_create_a_save(db):
    item = _make_item(db)

    with patch(
        "app.workers.share_parser_worker.get_oembed_data",
        return_value={"title": "Some Random Unmatched Place"},
    ), patch(
        "app.workers.share_parser_worker._find_best_place_match",
        return_value=(None, 0.1),
    ):
        _process_item(db, item)

    db.refresh(item)
    assert item.status == "unmatched"
    assert db.query(HitlistSave).filter(HitlistSave.user_id == item.submitted_by).count() == 0


def test_matched_share_with_no_submitted_by_does_not_error(db):
    city = _make_city(db)
    place = _make_place(db, city)
    item = _make_item(db, submitted_by=None)

    with patch(
        "app.workers.share_parser_worker.get_oembed_data",
        return_value={"title": place.name},
    ), patch(
        "app.workers.share_parser_worker._find_best_place_match",
        return_value=(place.id, 0.95),
    ):
        _process_item(db, item)  # must not raise

    db.refresh(item)
    assert item.status == "matched"
    assert db.query(HitlistSave).filter(HitlistSave.place_id == place.id).count() == 0
