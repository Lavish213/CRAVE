"""User-intent boundary between an imported share and a normal bookmark."""
from __future__ import annotations

import uuid

import pytest
from app.api.v1.routes.saves import SaveRequest, create_save, delete_save
from app.db.models.city import City
from app.db.models.crave_item import CraveItem
from app.db.models.hitlist_save import HitlistSave
from app.db.models.place import Place
from app.db.models.share_save_preference import ShareSavePreference
from app.db.session import SessionLocal
from app.workers.share_parser_worker import reconcile_matched_share_saves


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def test_unsave_blocks_reconciliation_and_explicit_resave_reenables_it(db):
    user_id = f"share-preference-{uuid.uuid4().hex[:12]}"

    city = City(
        id=str(uuid.uuid4()), name="Share preference city",
        slug=f"share-preference-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.2, is_active=True,
    )
    place = Place(
        id=str(uuid.uuid4()), name="Share preference place", city_id=city.id,
        lat=37.8, lng=-122.2, is_active=True,
    )
    db.add_all([city, place])
    db.commit()

    crave = CraveItem(url="https://example.com/share", submitted_by=user_id)
    crave.status = "matched"
    crave.matched_place_id = place.id
    save = HitlistSave(
        user_id=user_id, place_name=place.name, place_id=place.id,
        resolution_status="resolved", dedup_key=f"save:{user_id}:{place.id}",
    )
    db.add_all([crave, save])
    db.commit()

    removed = delete_save(place.id, db=db, user_id=user_id, _=None)
    assert removed["status"] == "deleted"
    assert db.get(ShareSavePreference, {"user_id": user_id, "place_id": place.id})

    assert reconcile_matched_share_saves(db) == 0
    assert db.query(HitlistSave).filter(HitlistSave.user_id == user_id).count() == 0

    resaved = create_save(SaveRequest(place_id=place.id), db=db, user_id=user_id, _=None)
    assert resaved["status"] == "saved"
    assert db.get(ShareSavePreference, {"user_id": user_id, "place_id": place.id}) is None
