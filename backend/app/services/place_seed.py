from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.category import Category
from app.db.models.place import Place
from app.services.place_normalizer import (
    normalize_category,
    compute_master_score,
)


VALID_OPEN = {"open", "likely_open", "unknown", "closed"}


def seed_places(
    *,
    db: Session,
    city_id: str,
    raw_places: list[dict[str, Any]],
) -> int:
    """
    FINAL canonical place seeder (LOCKED v4 - M2M safe)

    Guarantees:
    - Idempotent
    - Deterministic IDs
    - Many-to-many category safe
    - FK validation barrier
    - Batch never crashes
    - Handles dirty provider data
    """

    # --------------------------------------------------
    # Preload categories
    # --------------------------------------------------

    categories: dict[str, Category] = {
        c.slug: c for c in db.query(Category).all()
    }

    fallback_category = categories.get("other")
    if not fallback_category:
        raise RuntimeError("Missing required fallback category: 'other'")

    inserted = 0
    skipped = 0

    for raw in raw_places:
        try:
            # --------------------------------------------------
            # GEO REQUIRED
            # --------------------------------------------------

            lat = raw.get("lat")
            lng = raw.get("lng")

            if lat is None or lng is None:
                skipped += 1
                continue

            try:
                lat = float(lat)
                lng = float(lng)
            except Exception:
                skipped += 1
                continue

            # --------------------------------------------------
            # CATEGORY NORMALIZATION (MANY-TO-MANY)
            # --------------------------------------------------

            raw_category = raw.get("category") or "other"

            try:
                primary_slug = normalize_category(raw_category)
            except Exception:
                primary_slug = "other"

            category_list: list[Category] = []

            primary = categories.get(primary_slug)
            if primary:
                category_list.append(primary)

            # Always ensure fallback exists if nothing matched
            if not category_list:
                category_list.append(fallback_category)

            # Deduplicate (safety)
            category_list = list({c.id: c for c in category_list}.values())

            # --------------------------------------------------
            # DETERMINISTIC ID
            # --------------------------------------------------

            external_id = str(raw.get("id") or "")

            place_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{city_id}:{external_id}:{lat}:{lng}",
                )
            )

            if db.get(Place, place_id):
                continue

            # --------------------------------------------------
            # SAFE FLOAT PARSER
            # --------------------------------------------------

            def f(v, d):
                try:
                    return float(v)
                except Exception:
                    return d

            # --------------------------------------------------
            # SCORING
            # --------------------------------------------------

            taste_score = f(raw.get("taste_score"), 3.2)
            confidence_score = f(raw.get("confidence_score"), 0.55)
            operational_confidence = f(raw.get("operational_confidence"), 0.65)
            local_validation = f(raw.get("local_validation"), 0.0)
            hype_penalty = f(raw.get("hype_penalty"), 0.0)

            master_score, confidence_5 = compute_master_score(
                taste_score=taste_score,
                confidence_score=confidence_score,
                operational_confidence=operational_confidence,
                local_validation=local_validation,
                hype_penalty=hype_penalty,
            )

            # --------------------------------------------------
            # STATUS SAFE ENUM
            # --------------------------------------------------

            open_status = raw.get("open_status", "unknown")
            if open_status not in VALID_OPEN:
                open_status = "unknown"

            # --------------------------------------------------
            # NAME FALLBACK
            # --------------------------------------------------

            name = raw.get("name")
            if not isinstance(name, str) or not name.strip():
                name = place_id.replace("-", " ").title()

            # --------------------------------------------------
            # CREATE PLACE
            # --------------------------------------------------

            place = Place(
                name=name.strip(),
                city_id=city_id,
                lat=lat,
                lng=lng,
                price_tier=raw.get("price"),
                is_active=True,
            )

            # override deterministic id
            place.id = place_id

            # attach categories (M2M)
            place.categories = category_list

            db.add(place)

            # FK validation barrier
            db.flush()

            inserted += 1

        except Exception as e:
            db.rollback()
            print("Row failed:", e)
            skipped += 1
            continue

    db.commit()

    print(f"Inserted: {inserted}")
    print(f"Skipped: {skipped}")

    return inserted