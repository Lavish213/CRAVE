"""
Full Grubhub pipeline debug run — prints counts + sample data at every stage.
Uses the same mock payload as run_grubhub_pipeline.py (Grubhub blocks live scraping).
"""

from __future__ import annotations

import logging
import sys
import os

# ── ensure project root is on path ────────────────────────
ROOT = os.path.dirname(os.path.abspath(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

# ── DB bootstrap ──────────────────────────────────────────
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.models.base import Base
import app.db.models.city
import app.db.models.place
import app.db.models.category
import app.db.models.place_categories
import app.db.models.place_claim
import app.db.models.place_truth
import app.db.models.place_image
import app.db.models.menu_item
import app.db.models.menu_snapshot
import app.db.models.menu_source

from app.db.models.city import City
from app.db.models.place import Place

# ── Pipeline imports ──────────────────────────────────────
from app.services.menu.providers.grubhub_parser import parse_grubhub_payload
from app.services.menu.adapters.grubhub_adapter import adapt_grubhub_items
from app.services.menu.validation.validate_extracted_items import validate_extracted_items
from app.services.menu.menu_pipeline import process_extracted_menu
from app.services.menu.claims.menu_claim_emitter import emit_menu_claims
from app.services.menu.materialize_menu_truth import materialize_menu_truth
from app.services.menu.contracts import NormalizedMenuItem
from app.services.menu.normalization.fingerprint import build_menu_fingerprint
from app.services.menu.validation.validate_normalized_items import validate_normalized_items

logging.basicConfig(level=logging.WARNING)  # suppress noise; we print explicitly

PLACE_ID   = "test-place-grubhub-001"
PLACE_NAME = "Chipotle Mexican Grill (580 Market St, SF)"
CITY_ID    = "test-city-sf-001"

# ─────────────────────────────────────────────────────────
# MOCK PAYLOAD  (same structure as run_grubhub_pipeline.py)
# ─────────────────────────────────────────────────────────

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
                make_item(1001, "Burrito Bowl",         101, "Bowls",    1095, "Choice of protein with rice, beans, and toppings"),
                make_item(1002, "Burrito",              102, "Burritos", 1095, "Flour tortilla wrapped with your choice of filling"),
                make_item(1003, "Tacos (3)",            103, "Tacos",     995, "Crispy or soft corn tortillas"),
                make_item(1004, "Salad",                104, "Salads",   1095, "Romaine lettuce base with choice of protein"),
                make_item(1005, "Quesadilla",           102, "Burritos",  495, "Grilled flour tortilla with cheese"),
                make_item(1006, "Chips & Guacamole",   105, "Sides",     495, "Freshly made guacamole with tortilla chips"),
                make_item(1007, "Chips & Queso Blanco",105, "Sides",     395),
                make_item(1008, "Chips & Salsa",       105, "Sides",     295),
                make_item(1009, "Sofritas Bowl",        101, "Bowls",   1095, "Organic braised tofu with peppers and spices"),
                make_item(1010, "Veggie Bowl",          101, "Bowls",   1095, "Fresh veggies, fajita vegetables, guacamole"),
                make_item(1011, "Carnitas Burrito",     102, "Burritos", 1195, "Slow-cooked pulled pork"),
                make_item(1012, "Steak Bowl",           101, "Bowls",   1295, "Grilled adobo marinated steak"),
                make_item(1013, "Chicken Burrito",      102, "Burritos", 1095, "Adobo marinated grilled chicken"),
                make_item(1014, "Barbacoa Tacos",       103, "Tacos",   1095, "Braised beef barbacoa"),
                make_item(1015, "Water Bottle",         106, "Drinks",   195),
                make_item(1016, "Organic Milk",         106, "Drinks",   195),
                make_item(1017, "Izze Sparkling Juice", 106, "Drinks",  245),
                make_item(1018, "Large Fountain Drink", 106, "Drinks",  295),
            ]
        }
    }
}

# ─────────────────────────────────────────────────────────
# DB / SEED
# ─────────────────────────────────────────────────────────

def build_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    return Session()


def seed_place(db):
    city = City(
        id=CITY_ID, slug="san-francisco", name="San Francisco",
        state="CA", country="US", lat=37.7749, lng=-122.4194,
    )
    db.add(city)
    place = Place(
        id=PLACE_ID, name=PLACE_NAME, city_id=CITY_ID,
        lat=37.7749, lng=-122.4194, is_active=True,
    )
    db.add(place)
    db.commit()
    return place


# ─────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────

def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print('='*60)

def show(label, value):
    print(f"  {label}: {value}")

def show_item(prefix, item, i):
    if isinstance(item, dict):
        print(f"  {prefix}[{i}] name={item.get('name')} section={item.get('provider_category_name')} price_cents={item.get('base_price_cents')}")
    else:
        print(f"  {prefix}[{i}] name={getattr(item,'name',None)} section={getattr(item,'section',None)} price_cents={getattr(item,'price_cents',None)}")

FAIL = False

def check(condition, label):
    global FAIL
    mark = "OK" if condition else "FAIL"
    print(f"  [{mark}] {label}")
    if not condition:
        FAIL = True


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────

def main():
    global FAIL

    db = build_db()
    place = seed_place(db)

    # ─────────────────────────────────────
    # STEP 1 — URL RESOLUTION
    # ─────────────────────────────────────
    sep("STEP 1 — URL RESOLUTION")
    show("place_id",           place.id)
    show("place.grubhub_url",  getattr(place, "grubhub_url",      "N/A (not on model)"))
    show("place.menu_source_url", getattr(place, "menu_source_url","N/A (not on model)"))
    show("place.website",      getattr(place, "website",           "N/A (not on model)"))
    show("resolved URL",       "(using mock payload — Grubhub blocks live scraping)")
    print("  NOTE: mock payload injected directly, bypassing HTTP fetch")

    # ─────────────────────────────────────
    # STEP 2 — FETCHER
    # ─────────────────────────────────────
    sep("STEP 2 — FETCHER")
    payload = MOCK_GRUBHUB_PAYLOAD
    show("fetch succeeded",    True)
    show("payload is None",    False)
    show("payload top-level keys", list(payload.keys()))
    content = payload["object"]["data"]["content"]
    show("content item count", len(content))
    print(f"  first item keys: {list(content[0]['entity'].keys())[:8]}")
    print(f"  second item name: {content[1]['entity']['item_name']}")

    # ─────────────────────────────────────
    # STEP 3 — PARSER
    # ─────────────────────────────────────
    sep("STEP 3 — PARSER")
    raw_items = parse_grubhub_payload(payload)
    show("parsed item count", len(raw_items))
    for i, it in enumerate(raw_items[:2]):
        show_item("raw_item", it, i)
    check(len(raw_items) > 0,             "parsed items > 0")
    check(raw_items[0].get("name"),       "name exists on first item")
    check(raw_items[0].get("base_price_cents", 0) > 0, "base_price_cents > 0 on first item")
    check(raw_items[0].get("provider_category_name", "uncategorized") != "uncategorized",
          "provider_category_name not 'uncategorized' on first item")

    if not raw_items:
        print("\nFAILURE at STEP 3 — no items parsed"); sys.exit(1)

    # ─────────────────────────────────────
    # STEP 4 — ADAPTER
    # ─────────────────────────────────────
    sep("STEP 4 — ADAPTER")
    extracted = adapt_grubhub_items(raw_items)
    show("adapted item count", len(extracted))
    for i, it in enumerate(extracted[:2]):
        show_item("adapted", it, i)
    check(len(extracted) > 0,    "adapted items > 0")
    check(extracted[0].name,     "name set")
    check(extracted[0].section,  "section set")
    check(extracted[0].price_cents is not None and extracted[0].price_cents > 0,
          "price_cents valid and > 0")

    if not extracted:
        print("\nFAILURE at STEP 4 — adapter produced 0 items"); sys.exit(1)

    # ─────────────────────────────────────
    # STEP 5 — VALIDATION (EXTRACTED)
    # ─────────────────────────────────────
    sep("STEP 5 — VALIDATION (EXTRACTED)")
    count_before = len(extracted)
    validated = validate_extracted_items(extracted)
    count_after = len(validated)
    show("count before validation", count_before)
    show("count after validation",  count_after)
    dropped = count_before - count_after
    show("items dropped",           dropped)
    if count_before > 0 and dropped / count_before > 0.5:
        print("  WARNING: validation dropped >50% of items — may be too aggressive")
    check(count_after >= 2, "≥2 items survive validation")

    if not validated:
        print("\nFAILURE at STEP 5 — validation removed all items"); sys.exit(1)

    # ─────────────────────────────────────
    # STEP 6 — DEDUPE (ORCHESTRATOR KEY)
    # ─────────────────────────────────────
    sep("STEP 6 — DEDUPE (orchestrator-style fingerprint dedupe)")
    from app.services.menu.normalization.fingerprint import build_menu_fingerprint as bfp
    seen = set()
    deduped = []
    for item in validated:
        key = bfp(name=item.name, section=item.section or "uncategorized", currency=item.currency or "USD")
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    show("count after dedupe", len(deduped))
    check(len(deduped) >= 2, "≥2 items after dedupe")

    # ─────────────────────────────────────
    # STEP 7 — PIPELINE
    # ─────────────────────────────────────
    sep("STEP 7 — PIPELINE (process_extracted_menu)")
    canonical_menu = process_extracted_menu(validated)
    show("sections", len(canonical_menu.sections))
    show("total items", canonical_menu.item_count)
    if canonical_menu.sections:
        for sec in canonical_menu.sections[:3]:
            print(f"    section '{sec.name}': {len(sec.items)} items")
    check(canonical_menu.item_count >= 2, "≥2 canonical items")
    check(len(canonical_menu.sections) >= 1, "≥1 section")

    if canonical_menu.item_count < 2:
        print("\nFAILURE at STEP 7 — pipeline collapsed items"); sys.exit(1)

    # ─────────────────────────────────────
    # STEP 8 — FLATTEN
    # ─────────────────────────────────────
    sep("STEP 8 — FLATTEN")
    flat_items = []
    seen_fp = set()
    for section in canonical_menu.sections:
        for item in section.items:
            if not getattr(item, "section", None):
                item.section = section.name
            flat_items.append(item)
    show("flattened item count", len(flat_items))
    check(len(flat_items) >= 2, "≥2 flattened items")

    # ─────────────────────────────────────
    # STEP 9 — NORMALIZATION
    # ─────────────────────────────────────
    sep("STEP 9 — NORMALIZATION (build NormalizedMenuItem)")
    normalized_items = []
    seen_n = set()
    for item in flat_items:
        name     = getattr(item, "name",        None)
        section  = getattr(item, "section",     None) or "uncategorized"
        currency = getattr(item, "currency",    None) or "USD"
        if not name:
            continue
        fp = build_menu_fingerprint(name=name, section=section, currency=currency)
        if fp in seen_n:
            continue
        seen_n.add(fp)
        normalized_items.append(NormalizedMenuItem(
            name=name,
            section=section,
            price_cents=getattr(item, "price_cents", None),
            currency=currency,
            description=getattr(item, "description", None),
            fingerprint=fp,
            source_url=None,
        ))

    normalized_items = validate_normalized_items(normalized_items)
    show("normalized item count", len(normalized_items))
    for i, it in enumerate(normalized_items[:2]):
        print(f"  normalized[{i}] name={it.name} section={it.section} price={it.price_cents} fp={it.fingerprint[:12]}...")
    check(len(normalized_items) >= 2, "≥2 normalized items")

    if not normalized_items:
        print("\nFAILURE at STEP 9 — normalization removed all items"); sys.exit(1)

    # ─────────────────────────────────────
    # STEP 10 — CLAIMS
    # ─────────────────────────────────────
    sep("STEP 10 — CLAIMS (emit_menu_claims)")
    claims = emit_menu_claims(
        db=db,
        place_id=PLACE_ID,
        items=normalized_items,
        source="grubhub",
        confidence=0.9,
        weight=1.0,
    )
    show("claims emitted", len(claims or []))
    check(len(claims or []) >= 2, "≥2 claims emitted")

    if not claims:
        print("\nFAILURE at STEP 10 — no claims emitted"); sys.exit(1)

    # Commit so materializer can see them
    db.commit()

    # ─────────────────────────────────────
    # STEP 11 — MATERIALIZATION
    # ─────────────────────────────────────
    sep("STEP 11 — MATERIALIZATION")
    menu = materialize_menu_truth(db=db, place_id=PLACE_ID)
    show("menu created (not None)", menu is not None)
    if menu:
        show("materialized sections", len(menu.sections))
        show("materialized item count", menu.item_count)
    check(menu is not None,                     "menu is not None")
    check(menu is not None and menu.item_count >= 2, "≥2 items in final menu")

    # ─────────────────────────────────────
    # RESULT
    # ─────────────────────────────────────
    if menu and menu.item_count >= 2:
        sep("FINAL RESULT — SUCCESS")
        print(f"  Place: {PLACE_NAME}")
        print(f"  Sections: {len(menu.sections)}  |  Items: {menu.item_count}")
        print()
        for section in menu.sections:
            print(f"  [{section.name}]")
            for item in section.items:
                price = f"${item.price_cents/100:.2f}" if item.price_cents else "–"
                print(f"    {item.name:<40} {price}")
        sep("PIPELINE COMPLETE — NON-EMPTY MENU MATERIALIZED")
    else:
        sep("FINAL RESULT — FAILURE")
        print("  Pipeline did NOT produce a non-empty materialized menu.")
        print("  Review FAIL markers above to find the failing stage.")
        sys.exit(1)

    db.close()


if __name__ == "__main__":
    main()
