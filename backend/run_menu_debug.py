"""
Full Grubhub menu pipeline debug script.

Runs every stage and prints counts + sample data at each step.
Attempts a LIVE Grubhub fetch first; falls back to mock payload
if the fetch fails (Grubhub blocks most scraping attempts).

Usage:
    cd backend
    python run_menu_debug.py [--live-url <grubhub_url>]
"""
from __future__ import annotations

import json
import logging
import sys
import argparse

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── DB bootstrap ──────────────────────────────────────────────────────────────
from app.db.models.base import Base
import app.db.models.city              # noqa: F401
import app.db.models.place             # noqa: F401
import app.db.models.category          # noqa: F401
import app.db.models.place_categories  # noqa: F401
import app.db.models.place_claim       # noqa: F401
import app.db.models.place_truth       # noqa: F401
import app.db.models.place_image       # noqa: F401
import app.db.models.menu_item         # noqa: F401
import app.db.models.menu_snapshot     # noqa: F401
import app.db.models.menu_source       # noqa: F401

from app.db.models.city import City
from app.db.models.place import Place

# ── Pipeline imports ──────────────────────────────────────────────────────────
from app.services.menu.fetchers.grubhub_fetcher import (
    fetch_grubhub_menu,
    _resolve_grubhub_url,
)
from app.services.menu.providers.grubhub_parser import parse_grubhub_payload
from app.services.menu.adapters.grubhub_adapter import adapt_grubhub_items
from app.services.menu.validation.validate_extracted_items import validate_extracted_items
from app.services.menu.validation.validate_normalized_items import validate_normalized_items
from app.services.menu.menu_pipeline import process_extracted_menu
from app.services.menu.normalization.fingerprint import build_menu_fingerprint
from app.services.menu.contracts import NormalizedMenuItem
from app.services.menu.claims.menu_claim_emitter import emit_menu_claims
from app.services.menu.materialize_menu_truth import materialize_menu_truth

logging.basicConfig(level=logging.WARNING, format="%(levelname)s  %(name)s  %(message)s")

SEP = "=" * 68

PLACE_ID   = "debug-place-grubhub-001"
PLACE_NAME = "Chipotle Mexican Grill (580 Market St, SF)"
CITY_ID    = "debug-city-sf-001"

# ── Mock payload (matches grubhub_parser._classify_payload / _extract_content) ─
def _make_item(item_id, name, cat_id, cat_name, pickup_cents, desc=None):
    return {
        "entity": {
            "item_id": str(item_id),
            "item_name": name,
            "item_description": desc,
            "menu_category_id": str(cat_id),
            "menu_category_name": cat_name,
            "restaurant_id": "3239600",
            "available": True,
            "item_price": {
                "pickup": {
                    "value": pickup_cents,
                    "currency": "USD",
                    "styled_text": {"text": f"${pickup_cents/100:.2f}"},
                },
                "delivery": {"value": pickup_cents + 50, "currency": "USD"},
            },
            "features_v2": {},
        }
    }

MOCK_PAYLOAD = {
    "object": {
        "data": {
            "content": [
                _make_item(1001, "Burrito Bowl",           101, "Bowls",    1095, "Choice of protein with rice, beans, and toppings"),
                _make_item(1002, "Burrito",                102, "Burritos", 1095, "Flour tortilla with your choice of filling"),
                _make_item(1003, "Tacos (3)",              103, "Tacos",     995, "Crispy or soft corn tortillas"),
                _make_item(1004, "Salad",                  104, "Salads",   1095, "Romaine lettuce base with choice of protein"),
                _make_item(1005, "Quesadilla",             102, "Burritos",  495, "Grilled flour tortilla with cheese"),
                _make_item(1006, "Chips & Guacamole",      105, "Sides",     495, "Freshly made guacamole with tortilla chips"),
                _make_item(1007, "Chips & Queso Blanco",   105, "Sides",     395),
                _make_item(1008, "Chips & Salsa",          105, "Sides",     295),
                _make_item(1009, "Sofritas Bowl",          101, "Bowls",    1095, "Organic braised tofu with peppers and spices"),
                _make_item(1010, "Veggie Bowl",            101, "Bowls",    1095, "Fresh veggies, fajita vegetables, guacamole"),
                _make_item(1011, "Carnitas Burrito",       102, "Burritos", 1195, "Slow-cooked pulled pork"),
                _make_item(1012, "Steak Bowl",             101, "Bowls",    1295, "Grilled adobo marinated steak"),
                _make_item(1013, "Chicken Burrito",        102, "Burritos", 1095, "Adobo marinated grilled chicken"),
                _make_item(1014, "Barbacoa Tacos",         103, "Tacos",    1095, "Braised beef barbacoa"),
                _make_item(1015, "Water Bottle",           106, "Drinks",    195),
                _make_item(1016, "Organic Milk",           106, "Drinks",    195),
                _make_item(1017, "Izze Sparkling Juice",   106, "Drinks",    245),
                _make_item(1018, "Large Fountain Drink",   106, "Drinks",    295),
            ]
        }
    }
}

# ── DB helpers ────────────────────────────────────────────────────────────────
def build_db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autocommit=False, autoflush=False, expire_on_commit=False)
    return Session()


def seed_place(db, grubhub_url=None):
    city = City(
        id=CITY_ID, slug="san-francisco", name="San Francisco",
        state="CA", country="US", lat=37.7749, lng=-122.4194,
    )
    db.add(city)
    place = Place(
        id=PLACE_ID, name=PLACE_NAME, city_id=CITY_ID,
        lat=37.7749, lng=-122.4194, is_active=True,
    )
    place.grubhub_url = grubhub_url
    db.add(place)
    db.commit()
    return place


# ── Pretty helpers ────────────────────────────────────────────────────────────
def _fmt_item_extracted(item):
    return (
        f"  name={item.name!r}  section={item.section!r}  "
        f"price_cents={item.price_cents}  provider={item.provider!r}"
    )

def _fmt_item_normalized(item):
    return (
        f"  name={item.name!r}  section={item.section!r}  "
        f"price_cents={item.price_cents}  fp={item.fingerprint[:16]}..."
    )


# ── MAIN ──────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--live-url", default=None, help="Real Grubhub restaurant URL to attempt live fetch")
    args = parser.parse_args()

    live_url = args.live_url or "https://www.grubhub.com/restaurant/chipotle-mexican-grill-580-market-st-san-francisco/3239600"

    db = build_db()
    place = seed_place(db, grubhub_url=live_url)

    print(f"\n{SEP}")
    print("GRUBHUB MENU PIPELINE — FULL DEBUG RUN")
    print(SEP)

    # =========================================================================
    # STEP 1 — URL RESOLUTION
    # =========================================================================
    print("\n[STEP 1 — URL RESOLUTION]")
    print(f"  place_id          = {place.id}")
    print(f"  place.grubhub_url = {place.grubhub_url!r}")
    print(f"  place.menu_source_url = {getattr(place, 'menu_source_url', None)!r}")
    print(f"  place.website     = {getattr(place, 'website', None)!r}")

    resolved_url = _resolve_grubhub_url(place)
    print(f"  resolved URL      = {resolved_url!r}")

    if not resolved_url:
        print("  ❌ FAILURE: no Grubhub URL could be resolved — fetch will not run")
    else:
        print("  ✅ URL resolved")

    # =========================================================================
    # STEP 2 — FETCHER
    # =========================================================================
    print("\n[STEP 2 — FETCHER]")
    payload = None
    fetch_succeeded = False

    if resolved_url:
        print(f"  Attempting LIVE fetch → {resolved_url}")
        try:
            payload = fetch_grubhub_menu(place)
            fetch_succeeded = payload is not None
        except Exception as exc:
            print(f"  ⚠️  live fetch raised exception: {exc}")
            fetch_succeeded = False

    print(f"  fetch succeeded   = {fetch_succeeded}")
    print(f"  payload is None   = {payload is None}")

    if payload:
        print(f"  payload top-level keys = {list(payload.keys())[:8]}")
        # Show first 1-2 content items if nested
        try:
            content = payload["object"]["data"]["content"]
            print(f"  content list length   = {len(content)}")
            for c in content[:2]:
                print(f"    sample: {json.dumps(c, default=str)[:200]}")
        except (KeyError, TypeError):
            # Try flat structures
            for key in ("content", "menu", "menus", "data"):
                if key in payload:
                    val = payload[key]
                    print(f"  payload[{key!r}] type={type(val).__name__} len={len(val) if hasattr(val,'__len__') else 'N/A'}")
                    break
    else:
        print("  → falling back to MOCK payload")
        payload = MOCK_PAYLOAD
        print(f"  mock content items = {len(payload['object']['data']['content'])}")
        print("  ✅ mock payload ready")

    # =========================================================================
    # STEP 3 — PARSER
    # =========================================================================
    print("\n[STEP 3 — PARSER]")
    raw_items = parse_grubhub_payload(payload)
    print(f"  parsed item count = {len(raw_items)}")

    if raw_items:
        print("  first 2 parsed items:")
        for item in raw_items[:2]:
            name  = item.get("name", "MISSING")
            price = item.get("base_price_cents", "MISSING")
            cat   = item.get("provider_category_name", "MISSING")
            print(f"    name={name!r}  base_price_cents={price}  provider_category_name={cat!r}")

        # Verify
        names_ok  = all(item.get("name") for item in raw_items)
        prices_ok = any((item.get("base_price_cents") or 0) > 0 for item in raw_items)
        cats_ok   = any(item.get("provider_category_name", "uncategorized") != "uncategorized" for item in raw_items)
        print(f"  ✔ name exists on all items  = {names_ok}")
        print(f"  ✔ at least one price > 0    = {prices_ok}")
        print(f"  ✔ at least one real section = {cats_ok}")
    else:
        print("  ❌ FAILURE: parser returned 0 items")

    # =========================================================================
    # STEP 4 — ADAPTER
    # =========================================================================
    print("\n[STEP 4 — ADAPTER]")
    extracted = adapt_grubhub_items(raw_items)
    print(f"  adapted item count = {len(extracted)}")

    if extracted:
        print("  first 2 adapted items:")
        for item in extracted[:2]:
            print(_fmt_item_extracted(item))
        # Verify
        names_ok = all(item.name for item in extracted)
        price_ok = any((item.price_cents or 0) > 0 for item in extracted)
        print(f"  ✔ all have names        = {names_ok}")
        print(f"  ✔ at least one price>0  = {price_ok}")
    else:
        print("  ❌ FAILURE: adapter returned 0 items")

    # =========================================================================
    # STEP 5 — VALIDATION (EXTRACTED)
    # =========================================================================
    print("\n[STEP 5 — VALIDATION (EXTRACTED)]")
    count_before = len(extracted)
    validated = validate_extracted_items(extracted)
    count_after = len(validated)
    dropped = count_before - count_after

    print(f"  count before validation = {count_before}")
    print(f"  count after  validation = {count_after}")
    print(f"  dropped                 = {dropped}")

    if count_after == 0:
        print("  ❌ FAILURE: validation removed all items")
    elif dropped > count_before * 0.5:
        print(f"  ⚠️  WARNING: validation removed >50% of items ({dropped}/{count_before})")
    else:
        print("  ✅ validation OK")

    # =========================================================================
    # STEP 6 — DEDUPE (ORCHESTRATOR-STYLE)
    # =========================================================================
    print("\n[STEP 6 — DEDUPE]")
    seen_keys: set = set()
    deduped = []
    for item in validated:
        name     = getattr(item, "name", None) or ""
        section  = getattr(item, "section", None) or "uncategorized"
        currency = getattr(item, "currency", None) or "USD"
        if not name:
            continue
        key = build_menu_fingerprint(name=name, section=section, currency=currency)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        deduped.append(item)

    print(f"  count after dedupe = {len(deduped)}")
    if len(deduped) < 2:
        print("  ❌ FAILURE: dedupe collapsed items below minimum (2)")
    else:
        print("  ✅ dedupe OK")

    # =========================================================================
    # STEP 7 — PIPELINE (process_extracted_menu)
    # =========================================================================
    print("\n[STEP 7 — PIPELINE (process_extracted_menu)]")
    canonical_menu = process_extracted_menu(deduped)
    section_count  = len(canonical_menu.sections)
    total_items    = canonical_menu.item_count

    print(f"  number of sections = {section_count}")
    print(f"  total items        = {total_items}")

    for sec in canonical_menu.sections:
        print(f"    section={sec.name!r}  items={len(sec.items)}")

    if total_items < 2:
        print("  ❌ FAILURE: pipeline produced < 2 items — pipeline is collapsing items")
    else:
        print("  ✅ pipeline OK")

    # =========================================================================
    # STEP 8 — FLATTEN
    # =========================================================================
    print("\n[STEP 8 — FLATTEN]")
    flat_items = []
    for section in canonical_menu.sections:
        section_name = section.name or "uncategorized"
        for item in section.items:
            if not getattr(item, "section", None):
                item.section = section_name
            flat_items.append(item)

    print(f"  flattened item count = {len(flat_items)}")
    if not flat_items:
        print("  ❌ FAILURE: flatten produced 0 items")
    else:
        print("  ✅ flatten OK")

    # =========================================================================
    # STEP 9 — NORMALIZATION
    # =========================================================================
    print("\n[STEP 9 — NORMALIZATION]")
    seen_fps: set = set()
    normalized_items = []
    for item in flat_items:
        name     = (getattr(item, "name", None) or "").strip()
        section  = (getattr(item, "section", None) or "uncategorized").strip()
        currency = (getattr(item, "currency", None) or "USD").upper()
        if not name:
            continue
        fp = build_menu_fingerprint(name=name, section=section, currency=currency)
        if fp in seen_fps:
            continue
        seen_fps.add(fp)
        normalized_items.append(NormalizedMenuItem(
            name=name,
            section=section,
            price_cents=getattr(item, "price_cents", None),
            currency=currency,
            description=getattr(item, "description", None),
            fingerprint=fp,
        ))

    normalized_items = validate_normalized_items(normalized_items)
    print(f"  normalized item count = {len(normalized_items)}")

    if normalized_items:
        print("  first 2 normalized items:")
        for item in normalized_items[:2]:
            print(_fmt_item_normalized(item))
        print("  ✅ normalization OK")
    else:
        print("  ❌ FAILURE: normalization returned 0 items")

    # =========================================================================
    # STEP 10 — CLAIMS
    # =========================================================================
    print("\n[STEP 10 — CLAIMS]")
    claims = []
    if normalized_items:
        try:
            claims = emit_menu_claims(
                db=db,
                place_id=PLACE_ID,
                items=normalized_items,
                source="grubhub",
                confidence=0.9,
                weight=1.0,
            ) or []
        except Exception as exc:
            print(f"  ❌ FAILURE: emit_menu_claims raised: {exc}")

    print(f"  number of claims emitted = {len(claims)}")
    if not claims:
        print("  ❌ FAILURE: 0 claims emitted")
    else:
        print("  ✅ claims OK")

    # =========================================================================
    # STEP 11 — MATERIALIZATION
    # =========================================================================
    print("\n[STEP 11 — MATERIALIZATION]")
    menu = None
    try:
        menu = materialize_menu_truth(db=db, place_id=PLACE_ID)
    except Exception as exc:
        print(f"  ❌ FAILURE: materialize_menu_truth raised: {exc}")

    created = menu is not None
    print(f"  menu was created = {created}")

    if not created:
        print("  ❌ FAILURE: materialization returned None")
    else:
        print(f"  sections = {len(menu.sections)}  items = {menu.item_count}")
        print("  ✅ materialization OK")

    # =========================================================================
    # FINAL RESULT
    # =========================================================================
    print(f"\n{SEP}")

    if created and menu and menu.item_count > 0:
        print("✅ SUCCESS — non-empty materialized menu produced")
        print(f"   Sections: {len(menu.sections)}  |  Items: {menu.item_count}")
        print(SEP)
        for sec in menu.sections:
            print(f"\n  [{sec.name}]")
            for it in sec.items:
                price = f"${it.price_cents/100:.2f}" if it.price_cents else "–"
                print(f"    {it.name:<42} {price}")
    else:
        # Failure analysis
        print("❌ FAILURE — pipeline did not produce a non-empty materialized menu")
        print("\nFAILURE ANALYSIS:")
        stages = [
            ("URL resolution",   bool(resolved_url)),
            ("fetch/payload",    payload is not None),
            ("parser",           len(raw_items) > 0 if raw_items else False),
            ("adapter",          len(extracted) > 0 if extracted else False),
            ("validation",       len(validated) > 0 if validated else False),
            ("dedupe",           len(deduped) >= 2 if deduped else False),
            ("pipeline",         total_items >= 2),
            ("flatten",          len(flat_items) > 0 if flat_items else False),
            ("normalization",    len(normalized_items) > 0 if normalized_items else False),
            ("claims",           len(claims) > 0 if claims else False),
            ("materialization",  created),
        ]
        for stage, ok in stages:
            status = "✅" if ok else "❌ ← FAILURE POINT"
            print(f"  {stage:<20} {status}")

    print(f"\n{SEP}\n")
    db.close()


if __name__ == "__main__":
    main()
