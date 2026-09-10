from __future__ import annotations

import hashlib
import json
import uuid

from app.db.models.menu_item import MenuItem
from app.db.models.place import Place
from app.db.models.place_claim import PlaceClaim
from app.db.models.place_truth import PlaceTruth
from app.db.session import SessionLocal
from app.services.menu.claims.menu_claim_emitter import emit_menu_claims
from app.services.menu.contracts import ExtractedMenuItem, NormalizedMenuItem
from app.services.menu.materialize_menu_truth import materialize_menu_truth
from app.services.menu.menu_pipeline import process_extracted_menu
from app.services.menu.menu_publisher import MenuPublisher, is_obvious_placeholder_item
from app.services.menu.processing.menu_orchestrator import MenuOrchestrator


def _legacy_menu_hash_without_lineage(items):
    flat = [
        (
            (item["name"] or "").lower(),
            item.get("price_cents"),
            (item.get("currency") or "USD").upper(),
            (item.get("description") or "").lower(),
            item.get("fingerprint"),
        )
        for item in items
    ]
    flat.sort()
    raw = json.dumps(flat, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def test_placeholder_filter_is_narrow_and_requires_no_real_item_evidence():
    assert is_obvious_placeholder_item(name="Test", price_cents=0, description=None)
    assert is_obvious_placeholder_item(name="test2", price_cents=None, description="")
    assert is_obvious_placeholder_item(
        name="Placeholder item 4",
        price_cents=0,
        description=None,
    )

    assert not is_obvious_placeholder_item(
        name="Test Kitchen Burger",
        price_cents=0,
        description=None,
    )
    assert not is_obvious_placeholder_item(
        name="Test",
        price_cents=1200,
        description=None,
    )
    assert not is_obvious_placeholder_item(
        name="Test",
        price_cents=0,
        description="Seasonal tasting item",
    )


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
                    "external_menu_id": f"toast-{index}",
                    "source_type": "provider",
                    "source_url": "https://order.example/menu",
                },
                confidence=0.9,
                source="toast",
            ))
        db.commit()

        menu = materialize_menu_truth(db=db, place_id=place_id)
        assert menu is not None
        materialized_items = [
            item
            for section in menu.sections
            for item in section.items
        ]
        assert {item.provider_item_id for item in materialized_items} == {
            "toast-1",
            "toast-2",
        }

        truth = db.query(PlaceTruth).filter(
            PlaceTruth.place_id == place_id,
            PlaceTruth.truth_type == "menu",
        ).one()
        serialized_items = [
            item
            for section in truth.sources_json["sections"]
            for item in section["items"]
        ]
        assert {item["provider_item_id"] for item in serialized_items} == {
            "toast-1",
            "toast-2",
        }

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
        assert {row.raw_payload["provider_item_id"] for row in rows} == {
            "toast-1",
            "toast-2",
        }
    finally:
        db.rollback()
        db.query(MenuItem).filter(MenuItem.place_id == place_id).delete()
        db.query(PlaceClaim).filter(PlaceClaim.place_id == place_id).delete()
        db.query(PlaceTruth).filter(PlaceTruth.place_id == place_id).delete()
        db.query(Place).filter(Place.id == place_id).delete()
        db.commit()
        db.close()


def test_menu_pipeline_preserves_extracted_item_lineage():
    menu = process_extracted_menu([
        ExtractedMenuItem(
            name="Taco",
            section="Mains",
            price_cents=1200,
            currency="USD",
            description="Corn tortilla",
            image_url="https://cdn.example/taco.jpg",
            provider="html",
            provider_item_id="provider-taco",
            source_type="html",
            source_url="https://restaurant.example/menu",
        ),
        ExtractedMenuItem(
            name="Burrito",
            section="Mains",
            price_cents=1400,
            currency="USD",
            description="Bean and cheese",
            image_url="https://cdn.example/burrito.jpg",
            provider="html",
            provider_item_id="provider-burrito",
            source_type="html",
            source_url="https://restaurant.example/menu",
        ),
    ])

    items = [
        item
        for section in menu.sections
        for item in section.items
    ]

    assert menu.item_count == 2
    assert {item.provider for item in items} == {"html"}
    assert {item.source_type for item in items} == {"html"}
    assert {item.source_url for item in items} == {"https://restaurant.example/menu"}
    assert {item.provider_item_id for item in items} == {
        "provider-taco",
        "provider-burrito",
    }
    assert {item.image_url for item in items} == {
        "https://cdn.example/taco.jpg",
        "https://cdn.example/burrito.jpg",
    }


def test_orchestrator_run_with_items_publishes_item_source_url_from_extracted_items():
    db = SessionLocal()
    place_id = str(uuid.uuid4())
    try:
        db.add(Place(
            id=place_id,
            name=f"Canary Provenance Test {place_id[:8]}",
            city_id="00000000-0000-0000-0000-000000000001",
        ))
        db.commit()

        result = MenuOrchestrator().run_with_items(
            db=db,
            place_id=place_id,
            source="test_provenance_pipeline",
            items=[
                ExtractedMenuItem(
                    name="Taco",
                    section="Mains",
                    price_cents=1200,
                    currency="USD",
                    provider="html",
                    provider_item_id="provider-taco",
                    source_type="html",
                    source_url="https://restaurant.example/menu",
                ),
                ExtractedMenuItem(
                    name="Burrito",
                    section="Mains",
                    price_cents=1400,
                    currency="USD",
                    provider="html",
                    provider_item_id="provider-burrito",
                    source_type="html",
                    source_url="https://restaurant.example/menu",
                ),
            ],
        )
        db.commit()

        assert result.materialized is True
        assert result.emitted_claim_count == 2

        claims = db.query(PlaceClaim).filter(
            PlaceClaim.place_id == place_id,
            PlaceClaim.field == "menu_item",
        ).all()
        assert len(claims) == 2
        assert {claim.value_json["source_url"] for claim in claims} == {
            "https://restaurant.example/menu"
        }
        assert {claim.value_json["provider"] for claim in claims} == {"html"}
        assert {claim.value_json["source_type"] for claim in claims} == {"html"}
        assert {claim.value_json["external_menu_id"] for claim in claims} == {
            "provider-taco",
            "provider-burrito",
        }

        truth = db.query(PlaceTruth).filter(
            PlaceTruth.place_id == place_id,
            PlaceTruth.truth_type == "menu",
        ).one()
        serialized_items = [
            item
            for section in truth.sources_json["sections"]
            for item in section["items"]
        ]
        assert {item["provider_item_id"] for item in serialized_items} == {
            "provider-taco",
            "provider-burrito",
        }

        rows = db.query(MenuItem).filter(MenuItem.place_id == place_id).all()
        assert len(rows) == 2
        assert {row.provider for row in rows} == {"html"}
        assert {row.source_type for row in rows} == {"html"}
        assert {row.raw_payload["source_url"] for row in rows} == {
            "https://restaurant.example/menu"
        }
        assert {row.raw_payload["provider_item_id"] for row in rows} == {
            "provider-taco",
            "provider-burrito",
        }
    finally:
        db.rollback()
        db.query(MenuItem).filter(MenuItem.place_id == place_id).delete()
        db.query(PlaceClaim).filter(PlaceClaim.place_id == place_id).delete()
        db.query(PlaceTruth).filter(PlaceTruth.place_id == place_id).delete()
        db.query(Place).filter(Place.id == place_id).delete()
        db.commit()
        db.close()


def test_menu_claim_emitter_refuses_items_without_source_url_provenance():
    db = SessionLocal()
    place_id = str(uuid.uuid4())
    try:
        db.add(Place(
            id=place_id,
            name=f"Missing Provenance Test {place_id[:8]}",
            city_id="00000000-0000-0000-0000-000000000001",
        ))
        db.commit()

        emitted = emit_menu_claims(
            db=db,
            place_id=place_id,
            items=[
                NormalizedMenuItem(
                    name="Taco",
                    section="Mains",
                    price_cents=1200,
                    currency="USD",
                    fingerprint="taco-fp",
                ),
                NormalizedMenuItem(
                    name="Burrito",
                    section="Mains",
                    price_cents=1400,
                    currency="USD",
                    fingerprint="burrito-fp",
                ),
            ],
        )
        db.commit()

        assert emitted == []
        assert db.query(PlaceClaim).filter(
            PlaceClaim.place_id == place_id,
            PlaceClaim.field == "menu_item",
        ).count() == 0
    finally:
        db.rollback()
        db.query(PlaceClaim).filter(PlaceClaim.place_id == place_id).delete()
        db.query(Place).filter(Place.id == place_id).delete()
        db.commit()
        db.close()


def test_materialize_rewrites_legacy_truth_when_only_lineage_changes():
    db = SessionLocal()
    place_id = str(uuid.uuid4())
    try:
        db.add(Place(
            id=place_id,
            name=f"Legacy Truth Rewrite Test {place_id[:8]}",
            city_id="00000000-0000-0000-0000-000000000001",
        ))
        legacy_items = []
        for index, name in enumerate(("Taco", "Burrito"), start=1):
            fingerprint = f"legacy-{index}"
            legacy_items.append({
                "name": name,
                "section": "Mains",
                "price_cents": 1000 + index,
                "currency": "USD",
                "description": f"Fresh {name.lower()}",
                "fingerprint": fingerprint,
            })
            db.add(PlaceClaim(
                place_id=place_id,
                field="menu_item",
                claim_key=f"item-{index}",
                value_json={
                    **legacy_items[-1],
                    "provider": "toast",
                    "external_menu_id": f"toast-{index}",
                    "source_type": "provider",
                    "source_url": "https://order.example/menu",
                },
                confidence=0.9,
                source="toast",
            ))

        db.add(PlaceTruth(
            place_id=place_id,
            truth_type="menu",
            truth_value="menu",
            sources_json={
                "schema_version": 3,
                "built_at": "2026-09-01T00:00:00+00:00",
                "menu_hash": _legacy_menu_hash_without_lineage(legacy_items),
                "changes": {"added": 2, "removed": 0, "price_changed": 0},
                "sections": [
                    {
                        "name": "Mains",
                        "items": legacy_items,
                    }
                ],
                "metadata": {
                    "section_count": 1,
                    "item_count": 2,
                },
            },
            confidence=0.9,
        ))
        db.commit()

        menu = materialize_menu_truth(db=db, place_id=place_id)
        assert menu is not None
        db.commit()

        truth = db.query(PlaceTruth).filter(
            PlaceTruth.place_id == place_id,
            PlaceTruth.truth_type == "menu",
        ).one()
        serialized_items = [
            item
            for section in truth.sources_json["sections"]
            for item in section["items"]
        ]
        assert {item["provider_item_id"] for item in serialized_items} == {
            "toast-1",
            "toast-2",
        }
        assert {item["provider"] for item in serialized_items} == {"toast"}
        assert {item["source_type"] for item in serialized_items} == {"provider"}
        assert {item["source_url"] for item in serialized_items} == {
            "https://order.example/menu"
        }
        assert truth.sources_json["menu_hash"] != _legacy_menu_hash_without_lineage(
            legacy_items
        )
    finally:
        db.rollback()
        db.query(PlaceClaim).filter(PlaceClaim.place_id == place_id).delete()
        db.query(PlaceTruth).filter(PlaceTruth.place_id == place_id).delete()
        db.query(Place).filter(Place.id == place_id).delete()
        db.commit()
        db.close()


def test_orchestrator_source_url_fallback_only_when_entire_batch_needs_it():
    orchestrator = MenuOrchestrator()

    assert orchestrator._batch_source_url_fallback(
        [
            NormalizedMenuItem(
                name="Taco",
                section="Mains",
                price_cents=1200,
                currency="USD",
                fingerprint="taco",
            ),
            NormalizedMenuItem(
                name="Burrito",
                section="Mains",
                price_cents=1400,
                currency="USD",
                fingerprint="burrito",
            ),
        ],
        "https://restaurant.example/menu",
    ) == "https://restaurant.example/menu"

    assert orchestrator._batch_source_url_fallback(
        [
            NormalizedMenuItem(
                name="Taco",
                section="Mains",
                price_cents=1200,
                currency="USD",
                fingerprint="taco",
                source_url="https://provider.example/taco",
            ),
            NormalizedMenuItem(
                name="Burrito",
                section="Mains",
                price_cents=1400,
                currency="USD",
                fingerprint="burrito",
            ),
        ],
        "https://restaurant.example/menu",
    ) is None
