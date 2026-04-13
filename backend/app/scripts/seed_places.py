from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.category import Category
from app.db.models.place import Place, place_uuid
from app.services.place_normalizer import (
    normalize_category,
    normalize_price,
)

# ------------------------------------------------------------
# PATH (CWD SAFE)
# ------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data" / "places"


# ------------------------------------------------------------
# CORE SEEDER
# ------------------------------------------------------------

def seed_places_for_city(
    *,
    db: Session,
    city: City,
    raw_places: list[dict[str, Any]],
    categories: dict[str, Category],
) -> int:

    fallback_category = categories.get("other")
    if not fallback_category:
        raise RuntimeError("Missing required fallback category: 'other'")

    inserted = 0
    skipped = 0

    # 🔥 in-memory duplicate guard for this batch
    seen_ids: set[str] = set()

    for raw in raw_places:

        lat = raw.get("lat")
        lng = raw.get("lng")

        if lat is None or lng is None:
            skipped += 1
            continue

        try:
            lat = float(lat)
            lng = float(lng)
        except (TypeError, ValueError):
            skipped += 1
            continue

        name = (raw.get("name") or "").strip()
        if not name:
            skipped += 1
            continue

        # Deterministic ID (must match model logic)
        computed_id = place_uuid(name, city.id)

        # 🔥 Skip duplicates inside same JSON file
        if computed_id in seen_ids:
            skipped += 1
            continue

        # 🔥 Skip if already exists in DB (idempotent safe)
        if db.get(Place, computed_id):
            skipped += 1
            continue

        seen_ids.add(computed_id)

        # Category normalization
        try:
            category_slug = normalize_category(raw.get("category"))
        except Exception:
            category_slug = "other"

        category = categories.get(
            str(category_slug).lower(),
            fallback_category,
        )

        place = Place(
            name=name,
            city_id=city.id,
            lat=lat,
            lng=lng,
            price_tier=normalize_price(raw.get("price")),
            is_active=True,
        )

        place.categories = [category]

        db.add(place)
        inserted += 1

    print(f"   Inserted: {inserted}")
    print(f"   Skipped: {skipped}")

    return inserted


# ------------------------------------------------------------
# ENTRY POINT
# ------------------------------------------------------------

def main() -> None:

    db = SessionLocal()
    total_inserted = 0

    try:

        if not DATA_DIR.exists():
            raise RuntimeError("data/places directory not found")

        files = sorted(DATA_DIR.glob("*_v1.json"))

        if not files:
            raise RuntimeError("No *_v1.json files found in data/places")

        categories = {
            c.slug.lower(): c
            for c in db.query(Category).all()
        }

        if not categories:
            raise RuntimeError("No categories found. Seed categories first.")

        for file in files:

            print(f"\n🌎 Processing file: {file.name}")

            try:
                payload = json.loads(file.read_text(encoding="utf-8"))
            except Exception as e:
                print(f"❌ Failed to parse {file.name}: {e}")
                continue

            if not isinstance(payload, dict):
                print(f"⚠️ {file.name} invalid format — SKIP")
                continue

            city_slug = payload.get("city")
            raw_places = payload.get("places")

            if not city_slug or not isinstance(raw_places, list):
                print(f"⚠️ {file.name} missing required fields — SKIP")
                continue

            city = (
                db.query(City)
                .filter(City.slug == city_slug)
                .one_or_none()
            )

            if not city:
                print(f"❌ City '{city_slug}' not found — SKIP")
                continue

            if not raw_places:
                print(f"⚠️ {city_slug} has 0 places — SKIP")
                continue

            print(f"📦 Seeding {city.name}")

            try:
                inserted = seed_places_for_city(
                    db=db,
                    city=city,
                    raw_places=raw_places,
                    categories=categories,
                )
                db.commit()
                total_inserted += inserted
            except Exception as e:
                db.rollback()
                print(f"❌ Failed seeding {city_slug}: {e}")

    finally:
        db.close()

    print(f"\n🏁 Total places inserted: {total_inserted}\n")


if __name__ == "__main__":
    main()