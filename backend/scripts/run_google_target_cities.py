"""
Targeted Google Places enrichment for EMPTY/SPARSE cities.
Uses the Places API (New) - /v1/places:searchNearby (POST).
Bulk inserts candidates, then promotes via existing pipeline.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

import requests

_BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("google_target")

# ---------------------------------------------------------------------------
# Target cities with bounding boxes  (~0.10–0.11° radius)
# ---------------------------------------------------------------------------

TARGET_CITIES = {
    "stockton-ca": {
        "lat_min": 37.85, "lat_max": 38.07,
        "lon_min": -121.40, "lon_max": -121.18,
    },
    "milpitas": {
        "lat_min": 37.38, "lat_max": 37.49,
        "lon_min": -121.96, "lon_max": -121.84,
    },
    "pleasant-hill": {
        "lat_min": 37.89, "lat_max": 37.99,
        "lon_min": -122.12, "lon_max": -122.01,
    },
    "richmond": {
        "lat_min": 37.88, "lat_max": 37.98,
        "lon_min": -122.42, "lon_max": -122.28,
    },
    "santa-clara": {
        "lat_min": 37.30, "lat_max": 37.41,
        "lon_min": -122.02, "lon_max": -121.90,
    },
    "santa-rosa": {
        "lat_min": 38.39, "lat_max": 38.50,
        "lon_min": -122.77, "lon_max": -122.63,
    },
    "south-san-francisco": {
        "lat_min": 37.63, "lat_max": 37.68,
        "lon_min": -122.44, "lon_max": -122.38,
    },
    "union-city": {
        "lat_min": 37.56, "lat_max": 37.62,
        "lon_min": -122.08, "lon_max": -121.99,
    },
    "vallejo": {
        "lat_min": 38.06, "lat_max": 38.15,
        "lon_min": -122.32, "lon_max": -122.20,
    },
    "walnut-creek": {
        "lat_min": 37.87, "lat_max": 37.94,
        "lon_min": -122.10, "lon_max": -122.02,
    },
}

# ---------------------------------------------------------------------------
# Places API (New)
# ---------------------------------------------------------------------------

PLACES_API_URL = "https://places.googleapis.com/v1/places:searchNearby"
FIELD_MASK = (
    "places.id,places.displayName,places.location,"
    "places.formattedAddress,places.websiteUri,"
    "places.nationalPhoneNumber,places.types"
)
SEARCH_TYPES = ["restaurant", "cafe", "bar", "meal_takeaway"]
MAX_PER_CALL = 20
RADIUS_M = 1500
STEP_DEG = 1.5 / 111.0

_TYPE_TO_HINT: Dict[str, str] = {
    "restaurant": "restaurant",
    "cafe": "cafe",
    "bar": "bar",
    "bakery": "bakery",
    "meal_takeaway": "fast_food",
    "meal_delivery": "fast_food",
    "night_club": "bar",
    "ice_cream_shop": "dessert",
    "dessert_shop": "dessert",
    "sandwich_shop": "american",
    "pizza_restaurant": "pizza",
    "seafood_restaurant": "seafood",
    "sushi_restaurant": "japanese",
    "ramen_restaurant": "japanese",
    "mexican_restaurant": "mexican",
    "italian_restaurant": "italian",
    "chinese_restaurant": "chinese",
    "japanese_restaurant": "japanese",
    "korean_restaurant": "korean",
    "thai_restaurant": "thai",
    "indian_restaurant": "indian",
    "mediterranean_restaurant": "mediterranean",
    "barbecue_restaurant": "bbq",
    "american_restaurant": "american",
    "breakfast_restaurant": "breakfast",
    "brunch_restaurant": "breakfast",
    "fast_food_restaurant": "fast_food",
    "coffee_shop": "coffee",
    "tea_house": "coffee",
    "wine_bar": "bar",
    "sports_bar": "bar",
    "pub": "bar",
    "food_court": "restaurant",
    "diner": "american",
    "steakhouse": "american",
    "vegetarian_restaurant": "vegan",
    "vegan_restaurant": "vegan",
}

_GENERIC_TYPES = frozenset({
    "point_of_interest", "establishment", "premise",
    "food", "store", "health", "locality", "political", "geocode",
})


def _best_hint(types: List[str]) -> str:
    for t in types:
        h = _TYPE_TO_HINT.get(t)
        if h:
            return h
    for t in types:
        if t not in _GENERIC_TYPES:
            return t.replace("_", " ")
    return "restaurant"


def _search_nearby(api_key: str, lat: float, lon: float, place_type: str) -> List[Dict]:
    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "locationRestriction": {
            "circle": {
                "center": {"latitude": lat, "longitude": lon},
                "radius": float(RADIUS_M),
            }
        },
        "includedTypes": [place_type],
        "maxResultCount": MAX_PER_CALL,
    }
    try:
        r = requests.post(PLACES_API_URL, headers=headers, json=body, timeout=30)
        if r.status_code != 200:
            return []
        return r.json().get("places", [])
    except Exception as exc:
        logger.debug("places_api_exception lat=%s lon=%s error=%s", lat, lon, exc)
        return []


def scan_city_grid(api_key: str, bbox: Dict) -> List[Dict]:
    cells = []
    lat = bbox["lat_min"]
    while lat <= bbox["lat_max"]:
        lon = bbox["lon_min"]
        while lon <= bbox["lon_max"]:
            cells.append((lat, lon))
            lon += STEP_DEG
        lat += STEP_DEG

    seen_ids: Set[str] = set()
    records: List[Dict] = []

    for i, (lat, lon) in enumerate(cells):
        for place_type in SEARCH_TYPES:
            places = _search_nearby(api_key, lat, lon, place_type)
            for p in places:
                place_id = p.get("id", "")
                if place_id and place_id in seen_ids:
                    continue
                if place_id:
                    seen_ids.add(place_id)
                types: List[str] = p.get("types") or []
                name = p.get("displayName", {}).get("text")
                loc = p.get("location", {})
                plat = loc.get("latitude")
                plng = loc.get("longitude")
                if not name or plat is None or plng is None:
                    continue
                records.append({
                    "external_id": f"google:{place_id}",
                    "name": name,
                    "address": p.get("formattedAddress"),
                    "lat": float(plat),
                    "lng": float(plng),
                    "phone": p.get("nationalPhoneNumber"),
                    "website": p.get("websiteUri"),
                    "category_hint": _best_hint(types),
                    "raw_payload": p,
                })
        if i % 50 == 0:
            logger.debug("grid_progress cells=%s/%s records=%s", i, len(cells), len(records))

    return records


def bulk_insert_candidates(db, records: List[Dict], city_id: str) -> tuple[int, int]:
    """Bulk insert candidates, skipping existing external_ids."""
    from sqlalchemy import text

    if not records:
        return 0, 0

    # Get all existing external_ids for this source to skip
    existing_ids = set(
        r[0] for r in db.execute(text(
            "SELECT external_id FROM discovery_candidates WHERE source='google_places' AND external_id IS NOT NULL"
        )).fetchall()
    )
    logger.info("existing_google_external_ids=%s", len(existing_ids))

    now = datetime.now(timezone.utc).isoformat()
    inserted = 0
    skipped = 0
    errors = 0
    batch = []

    for rec in records:
        ext_id = rec.get("external_id")
        if ext_id and ext_id in existing_ids:
            skipped += 1
            continue

        raw = rec.get("raw_payload") or {}
        if isinstance(raw, dict):
            raw = json.dumps(raw)

        batch.append({
            "id": str(uuid.uuid4()),
            "external_id": ext_id,
            "source": "google_places",
            "name": rec["name"],
            "city_id": city_id,
            "lat": rec.get("lat"),
            "lng": rec.get("lng"),
            "address": rec.get("address"),
            "phone": rec.get("phone"),
            "website": rec.get("website"),
            "category_hint": rec.get("category_hint"),
            "confidence_score": 0.85,
            "status": "candidate",
            "resolved": 0,
            "blocked": 0,
            "raw_payload": raw,
            "created_at": now,
            "updated_at": now,
        })

        if len(batch) >= 500:
            try:
                db.execute(text("""
                    INSERT OR IGNORE INTO discovery_candidates
                    (id, external_id, source, name, city_id, lat, lng, address,
                     phone, website, category_hint, confidence_score, status,
                     resolved, blocked, raw_payload, created_at, updated_at)
                    VALUES
                    (:id, :external_id, :source, :name, :city_id, :lat, :lng, :address,
                     :phone, :website, :category_hint, :confidence_score, :status,
                     :resolved, :blocked, :raw_payload, :created_at, :updated_at)
                """), batch)
                db.commit()
                inserted += len(batch)
                logger.info("bulk_insert_progress inserted=%s", inserted)
                batch = []
            except Exception as e:
                db.rollback()
                errors += 1
                logger.warning("batch_error: %s", e)
                batch = []

    if batch:
        try:
            db.execute(text("""
                INSERT OR IGNORE INTO discovery_candidates
                (id, external_id, source, name, city_id, lat, lng, address,
                 phone, website, category_hint, confidence_score, status,
                 resolved, blocked, raw_payload, created_at, updated_at)
                VALUES
                (:id, :external_id, :source, :name, :city_id, :lat, :lng, :address,
                 :phone, :website, :category_hint, :confidence_score, :status,
                 :resolved, :blocked, :raw_payload, :created_at, :updated_at)
            """), batch)
            db.commit()
            inserted += len(batch)
        except Exception as e:
            db.rollback()
            errors += len(batch)
            logger.warning("final_batch_error: %s", e)

    return inserted, skipped


def run() -> None:
    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        logger.error("GOOGLE_PLACES_API_KEY not set")
        sys.exit(1)

    from app.db.session import SessionLocal
    from app.db.models.city import City
    from app.db.models.place import Place
    from sqlalchemy import func, text

    # Before metrics
    db = SessionLocal()
    before_places = db.query(func.count(Place.id)).filter(Place.is_active.is_(True)).scalar()
    logger.info("before_places=%s", before_places)
    db.close()

    grand_total_inserted = 0

    for city_slug, bbox in TARGET_CITIES.items():
        logger.info("=== google_city_start city=%s ===", city_slug)

        db = SessionLocal()
        try:
            city = db.query(City).filter(City.slug == city_slug).one_or_none()
            if not city:
                logger.warning("city_not_found slug=%s — skipping", city_slug)
                continue

            records = scan_city_grid(api_key, bbox)
            logger.info("google_fetched city=%s count=%s", city_slug, len(records))

            if not records:
                logger.warning("google_no_results city=%s", city_slug)
                continue

            inserted, skipped = bulk_insert_candidates(db, records, city.id)
            logger.info("google_city_done city=%s inserted=%s skipped=%s",
                        city_slug, inserted, skipped)
            grand_total_inserted += inserted

        finally:
            db.close()

        time.sleep(0.5)

    logger.info("google_all_cities_done total_inserted=%s", grand_total_inserted)

    # STEP 3 — Promote
    logger.info("=== STEP 3: PROMOTING GOOGLE CANDIDATES ===")
    from app.db.session import SessionLocal as SL
    from app.services.discovery.pipeline_v2 import run_discovery_pipeline_v2

    db2 = SL()
    try:
        result = run_discovery_pipeline_v2(db=db2, limit=20000)
        db2.commit()
        logger.info("promote_done result=%s", result)
    except Exception:
        db2.rollback()
        raise
    finally:
        db2.close()

    # STEP 4 — After metrics
    db3 = SL()
    try:
        after_places = db3.query(func.count(Place.id)).filter(Place.is_active.is_(True)).scalar()
        with_cat = db3.execute(
            text("SELECT COUNT(DISTINCT place_id) FROM place_categories")
        ).scalar()
        with_website = db3.query(func.count(Place.id)).filter(
            Place.is_active.is_(True), Place.website.isnot(None)
        ).scalar()
        no_geo = db3.query(func.count(Place.id)).filter(
            Place.is_active.is_(True), Place.lat.is_(None)
        ).scalar()

        logger.info("=== STEP 4: RESULTS ===")
        logger.info("places_before=%s", before_places)
        logger.info("places_after=%s  delta=+%s", after_places, after_places - before_places)
        logger.info("pct_with_category=%.1f%%", (with_cat / after_places * 100) if after_places else 0.0)
        logger.info("pct_with_website=%.1f%%", (with_website / after_places * 100) if after_places else 0.0)
        logger.info("places_missing_coords=%s", no_geo)

        # STEP 5 — City check
        logger.info("=== STEP 5: CITY CHECK ===")
        city_rows = db3.execute(text("""
            SELECT c.slug, COUNT(p.id) n
            FROM cities c
            LEFT JOIN places p ON p.city_id = c.id AND p.is_active = 1
            WHERE c.slug IN (
                'stockton-ca','milpitas','pleasant-hill','richmond','santa-clara',
                'santa-rosa','south-san-francisco','union-city','vallejo','walnut-creek'
            )
            GROUP BY c.slug
            ORDER BY n DESC
        """)).fetchall()
        for slug, n in city_rows:
            status = "STRONG" if n >= 100 else ("SPARSE" if n > 0 else "EMPTY")
            logger.info("  %s  %s: %s places", status, slug, n)

    finally:
        db3.close()


if __name__ == "__main__":
    run()
