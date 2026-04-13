"""
Run the full Grubhub menu pipeline for one known place.

Pipeline:
  mock Grubhub JSON payload (Grubhub blocks scraping)
  → parse_grubhub_payload
  → adapt_grubhub_items
  → validate_extracted_items
  → process_extracted_menu
  → emit_menu_claims
  → materialize_menu_truth
  → print result

The mock payload matches the exact format grubhub_parser.py expects,
based on _classify_payload and _extract_content logic.
"""

from __future__ import annotations

import logging
import sys

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

# ── DB bootstrap ──────────────────────────────────────────
from app.db.models.base import Base
import app.db.models.city               # noqa: F401
import app.db.models.place              # noqa: F401
import app.db.models.category           # noqa: F401
import app.db.models.place_categories   # noqa: F401
import app.db.models.place_claim        # noqa: F401
import app.db.models.place_truth        # noqa: F401
import app.db.models.place_image        # noqa: F401
import app.db.models.menu_item          # noqa: F401
import app.db.models.menu_snapshot      # noqa: F401
import app.db.models.menu_source        # noqa: F401

from app.db.models.city import City
from app.db.models.place import Place

# ── Pipeline ──────────────────────────────────────────────
from app.services.menu.providers.grubhub_parser import parse_grubhub_payload
from app.services.menu.adapters.grubhub_adapter import adapt_grubhub_items
from app.services.menu.validation.validate_extracted_items import validate_extracted_items
from app.services.menu.menu_pipeline import process_extracted_menu
from app.services.menu.claims.menu_claim_emitter import emit_menu_claims
from app.services.menu.materialize_menu_truth import materialize_menu_truth

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s  %(name)s  %(message)s",
)
log = logging.getLogger("grubhub_pipeline_run")


PLACE_ID = "test-place-grubhub-001"
PLACE_NAME = "Chipotle Mexican Grill (580 Market St, SF)"
CITY_ID = "test-city-sf-001"


# ──────────────────────────────────────────────────────────
# MOCK GRUBHUB PAYLOAD
# Matches the exact shape grubhub_parser._extract_content and
# _classify_payload expect:
#   payload["object"]["data"]["content"] = list of {entity: {...}}
#   entity has item_id, item_name, item_price (simple_item type)
# ──────────────────────────────────────────────────────────

def make_item(item_id, name, category_id, category_name, pickup_cents, description=None):
    return {
        "entity": {
            "item_id": str(item_id),
            "item_name": name,
            "item_description": description,
            "menu_category_id": str(category_id),
            "menu_category_name": category_name,
            "restaurant_id": "3239600",
            "available": True,
            "item_price": {
                "pickup": {
                    "value": pickup_cents,
                    "currency": "USD",
                    "styled_text": {"text": f"${pickup_cents/100:.2f}"},
                },
                "delivery": {
                    "value": pickup_cents + 50,
                    "currency": "USD",
                },
            },
            "features_v2": {},
        }
    }


MOCK_GRUBHUB_PAYLOAD = {
    "object": {
        "data": {
            "content": [
                make_item(1001, "Burrito Bowl", 101, "Bowls", 1095, "Choice of protein with rice, beans, and toppings"),
                make_item(1002, "Burrito", 102, "Burritos", 1095, "Flour tortilla wrapped with your choice of filling"),
                make_item(1003, "Tacos (3)", 103, "Tacos", 995, "Crispy or soft corn tortillas"),
                make_item(1004, "Salad", 104, "Salads", 1095, "Romaine lettuce base with choice of protein"),
                make_item(1005, "Quesadilla", 102, "Burritos", 495, "Grilled flour tortilla with cheese"),
                make_item(1006, "Chips & Guacamole", 105, "Sides", 495, "Freshly made guacamole with tortilla chips"),
                make_item(1007, "Chips & Queso Blanco", 105, "Sides", 395),
                make_item(1008, "Chips & Salsa", 105, "Sides", 295),
                make_item(1009, "Sofritas Bowl", 101, "Bowls", 1095, "Organic braised tofu with peppers and spices"),
                make_item(1010, "Veggie Bowl", 101, "Bowls", 1095, "Fresh veggies, fajita vegetables, guacamole"),
                make_item(1011, "Carnitas Burrito", 102, "Burritos", 1195, "Slow-cooked pulled pork"),
                make_item(1012, "Steak Bowl", 101, "Bowls", 1295, "Grilled adobo marinated steak"),
                make_item(1013, "Chicken Burrito", 102, "Burritos", 1095, "Adobo marinated grilled chicken"),
                make_item(1014, "Barbacoa Tacos", 103, "Tacos", 1095, "Braised beef barbacoa"),
                make_item(1015, "Water Bottle", 106, "Drinks", 195),
                make_item(1016, "Organic Milk", 106, "Drinks", 195),
                make_item(1017, "Izze Sparkling Juice", 106, "Drinks", 245),
                make_item(1018, "Large Fountain Drink", 106, "Drinks", 295),
            ]
        }
    }
}


# ──────────────────────────────────────────────────────────
# STEP 1: In-memory SQLite DB
# ──────────────────────────────────────────────────────────

def build_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    return Session


# ──────────────────────────────────────────────────────────
# STEP 2: Seed minimal DB records
# ──────────────────────────────────────────────────────────

def seed_place(db):
    city = City(
        id=CITY_ID,
        slug="san-francisco",
        name="San Francisco",
        state="CA",
        country="US",
        lat=37.7749,
        lng=-122.4194,
    )
    db.add(city)

    place = Place(
        id=PLACE_ID,
        name=PLACE_NAME,
        city_id=CITY_ID,
        lat=37.7749,
        lng=-122.4194,
        is_active=True,
    )
    db.add(place)
    db.commit()
    return place


# ──────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────

def main():
    # DB
    Session = build_db()
    db = Session()

    place = seed_place(db)
    log.info("place seeded id=%s", place.id)

    # Payload (mock — Grubhub blocks direct scraping)
    payload = MOCK_GRUBHUB_PAYLOAD
    log.info("using mock grubhub payload items=%s", len(payload["object"]["data"]["content"]))

    # Parse
    raw_items = parse_grubhub_payload(payload)
    log.info("parsed raw_items=%s", len(raw_items))

    if not raw_items:
        log.error("no items parsed from payload — check GRUBHUB_RESTAURANT_ID")
        # Show payload shape for debugging
        top_keys = list(payload.keys())[:10]
        log.error("payload top-level keys: %s", top_keys)
        sys.exit(1)

    # Adapt
    extracted = adapt_grubhub_items(raw_items)
    log.info("adapted extracted=%s", len(extracted))

    # Validate
    validated = validate_extracted_items(extracted)
    log.info("validated count=%s", len(validated))

    # Normalize + dedupe via pipeline
    canonical_menu = process_extracted_menu(validated)
    log.info(
        "canonical sections=%s items=%s",
        len(canonical_menu.sections),
        canonical_menu.item_count,
    )

    if canonical_menu.item_count == 0:
        log.error("pipeline produced 0 items")
        sys.exit(1)

    # Emit claims
    from app.services.menu.orchestration.menu_item_normalizer import normalize_menu_items
    # Build NormalizedMenuItems from canonical
    from app.services.menu.contracts import NormalizedMenuItem
    from app.services.menu.normalization.fingerprint import build_menu_fingerprint

    normalized_items = []
    seen = set()
    for section in canonical_menu.sections:
        for item in section.items:
            fp = item.fingerprint or build_menu_fingerprint(
                name=item.name,
                section=section.name,
                currency=item.currency or "USD",
            )
            if fp in seen:
                continue
            seen.add(fp)
            normalized_items.append(NormalizedMenuItem(
                name=item.name,
                section=section.name,
                price_cents=item.price_cents,
                currency=item.currency or "USD",
                description=item.description,
                fingerprint=fp,
            ))

    claims = emit_menu_claims(
        db=db,
        place_id=PLACE_ID,
        items=normalized_items,
        source="grubhub",
        confidence=0.9,
        weight=1.0,
    )
    log.info("emitted claims=%s", len(claims or []))

    # Materialize
    menu = materialize_menu_truth(db=db, place_id=PLACE_ID)

    if not menu:
        log.error("materialize returned None")
        sys.exit(1)

    # ── Print result ──────────────────────────────────────
    print("\n" + "=" * 60)
    print(f"MATERIALIZED MENU: {PLACE_NAME}")
    print(f"Sections: {len(menu.sections)}  |  Items: {menu.item_count}")
    print("=" * 60)

    for section in menu.sections:
        print(f"\n  [{section.name}]")
        for item in section.items:
            price = f"${item.price_cents/100:.2f}" if item.price_cents else "–"
            desc = f"  {item.description[:60]}..." if item.description else ""
            print(f"    {item.name:<40} {price}{desc}")

    print("\n" + "=" * 60)
    print("PIPELINE COMPLETE")
    print("=" * 60)

    db.close()


if __name__ == "__main__":
    main()
