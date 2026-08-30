from __future__ import annotations

import uuid

from app.db.models.menu_item import MenuItem
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.session import SessionLocal
from app.services.menu.materialize_menu_truth import materialize_menu_truth
from app.services.menu.menu_publisher import MenuPublisher


def test_menu_truth_and_publisher_preserve_item_lineage_but_never_publish_a_raw_image_url():
    db = SessionLocal()
    place_id = str(uuid.uuid4())
    try:
        db.add(Place(
            id=place_id,
            name=f"Provenance Test {place_id[:8]}",
            city_id="00000000-0000-0000-0000-000000000001",
        ))
        for index, name in enumerate(("Taco", "Burrito"), start=1):
            db.add(PlaceClaim(
                place_id=place_id,
                field="menu_item",
                claim_key=f"item-{index}",
                value_json={
                    "fingerprint": f"item-{index}",
                    "name": name,
                    "section": "Mains",
                    "price_cents": 1000 + index,
                    "currency": "USD",
                    "description": f"Fresh {name.lower()}",
                    "image_url": f"https://cdn.example/{index}.jpg",
                    "provider": "toast",
                    "source_type": "provider",
                    "source_url": "https://order.example/menu",
                },
                confidence=0.9,
                source="toast",
            ))
        db.commit()

        menu = materialize_menu_truth(db=db, place_id=place_id)
        assert menu is not None
        assert MenuPublisher().publish(place_id=place_id, db=db) == 2
        db.commit()

        rows = db.query(MenuItem).filter(MenuItem.place_id == place_id).all()
        assert {row.provider for row in rows} == {"toast"}
        assert {row.source_type for row in rows} == {"provider"}
        # image_url is a real field on the claim, but MenuItem.image must
        # never be set directly from it -- only MenuImageBridge.ingest() is
        # allowed to populate an item image, since it runs classification
        # and visibility assignment first ("No bypass. Phase 3 is law.").
        # Publishing the raw extracted URL here would put an unmoderated
        # external image directly in front of users.
        assert {row.image for row in rows} == {None}
        assert {row.raw_payload["source_url"] for row in rows} == {
            "https://order.example/menu"
        }
    finally:
        db.rollback()
        db.query(MenuItem).filter(MenuItem.place_id == place_id).delete()
        db.query(PlaceClaim).filter(PlaceClaim.place_id == place_id).delete()
        from app.db.models.place_truth import PlaceTruth
        db.query(PlaceTruth).filter(PlaceTruth.place_id == place_id).delete()
        db.query(Place).filter(Place.id == place_id).delete()
        db.commit()
        db.close()
