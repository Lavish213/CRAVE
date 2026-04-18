"""
Category backfill script.

Reads category signals from discovery_candidates (category_hint, raw_payload OSM tags)
and inserts rows into place_categories for places that have no category or only "Other".

Rules:
- Only update places with no category OR only "Other"
- Never overwrite valid non-Other categories
- Signal priority: OSM cuisine > OSM amenity > category_hint > name keywords
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Category ID map (from DB)
# ---------------------------------------------------------------------------

CAT = {
    "Mexican":       "00b06025-0e1e-5f2a-ba7d-b22996fdee25",
    "Italian":       "1758c081-4d4e-50b7-9f2a-ab3ada2d7413",
    "Chinese":       "e64f9147-403e-5fe2-a5b1-048572eec3bf",
    "Japanese":      "e7df6364-4252-5d48-b451-f2d5eabe707b",
    "Korean":        "42ab72fb-3b3a-55ca-b50c-3ef268d91eea",
    "Thai":          "d94ea985-34ae-5b7f-8f1b-4a0c04b641ae",
    "Indian":        "885075c3-132a-5150-a0dd-05b11b835de5",
    "Mediterranean": "4c102901-5324-5b90-9fed-6914c68f42c6",
    "American":      "45ae1d76-e1bf-5c8d-a139-0acd642e0376",
    "BBQ":           "74599537-ae78-5226-875e-bcb367247218",
    "Seafood":       "247e9e45-3c33-5f83-98f7-ce4622f5052e",
    "Pizza":         "42a11991-d01d-5daf-8fdf-f840057fb3c2",
    "Breakfast":     "c72f88ab-4a7a-5d21-a390-47da2924b7d5",
    "Coffee":        "c8920489-8222-5aaf-ba77-81bbde6f2d09",
    "Desserts":      "d41cb7c9-25c4-5f27-b8ba-dcaa6e57a12a",
    "Other":         "97ee17ef-a9ac-5079-8527-4448c07f1c23",
    "Restaurant":    "660b5eae-cf5e-5e15-8ae6-5b5c66199d6e",
    "Cafe":          "8d2f5e7a-00f2-56ea-8ad5-17b00e8549ce",
    "Bar":           "76fc27fe-b407-5d2c-b330-b5194b678730",
    "Fine Dining":   "59c91ed1-628c-50db-8345-3938e5faf090",
    "Fast Casual":   "fd6c57eb-c3f8-59b0-b533-c42237412e28",
}

OTHER_ID = CAT["Other"]

# ---------------------------------------------------------------------------
# Signal → Category mappings
# ---------------------------------------------------------------------------

# OSM cuisine tag → category
CUISINE_MAP: dict[str, str] = {
    "mexican":        CAT["Mexican"],
    "tex-mex":        CAT["Mexican"],
    "italian":        CAT["Italian"],
    "pizza":          CAT["Pizza"],
    "chinese":        CAT["Chinese"],
    "japanese":       CAT["Japanese"],
    "sushi":          CAT["Japanese"],
    "korean":         CAT["Korean"],
    "thai":           CAT["Thai"],
    "indian":         CAT["Indian"],
    "mediterranean":  CAT["Mediterranean"],
    "greek":          CAT["Mediterranean"],
    "lebanese":       CAT["Mediterranean"],
    "turkish":        CAT["Mediterranean"],
    "american":       CAT["American"],
    "burger":         CAT["American"],
    "chicken":        CAT["American"],
    "bbq":            CAT["BBQ"],
    "barbecue":       CAT["BBQ"],
    "seafood":        CAT["Seafood"],
    "fish":           CAT["Seafood"],
    "breakfast":      CAT["Breakfast"],
    "coffee_shop":    CAT["Coffee"],
    "coffee":         CAT["Coffee"],
    "bubble_tea":     CAT["Coffee"],
    "ice_cream":      CAT["Desserts"],
    "frozen_yogurt":  CAT["Desserts"],
    "donut":          CAT["Desserts"],
    "dessert":        CAT["Desserts"],
    "cake":           CAT["Desserts"],
    "sandwich":       CAT["Restaurant"],
    "vietnamese":     CAT["Restaurant"],
    "filipino":       CAT["Restaurant"],
    "asian":          CAT["Restaurant"],
    "caribbean":      CAT["Restaurant"],
    "french":         CAT["Fine Dining"],
    "juice":          CAT["Cafe"],
}

# OSM amenity tag → category
AMENITY_MAP: dict[str, str] = {
    "restaurant":    CAT["Restaurant"],
    "fast_food":     CAT["Fast Casual"],
    "cafe":          CAT["Cafe"],
    "coffee_shop":   CAT["Coffee"],
    "bar":           CAT["Bar"],
    "pub":           CAT["Bar"],
    "biergarten":    CAT["Bar"],
    "ice_cream":     CAT["Desserts"],
    "confectionery": CAT["Desserts"],
    "food_court":    CAT["Restaurant"],
    "canteen":       CAT["Restaurant"],
    "deli":          CAT["Restaurant"],
}

# category_hint → category
HINT_MAP: dict[str, str] = {
    "restaurant":      CAT["Restaurant"],
    "fast_food":       CAT["Fast Casual"],
    "cafe":            CAT["Cafe"],
    "bar":             CAT["Bar"],
    "pub":             CAT["Bar"],
    "bakery":          CAT["Breakfast"],
    "dessert":         CAT["Desserts"],
    "ice_cream":       CAT["Desserts"],
    "confectionery":   CAT["Desserts"],
    "pastry":          CAT["Desserts"],
    "deli":            CAT["Restaurant"],
    "food_court":      CAT["Restaurant"],
    "biergarten":      CAT["Bar"],
    "american":        CAT["American"],
    "mexican":         CAT["Mexican"],
    "chinese":         CAT["Chinese"],
    "japanese":        CAT["Japanese"],
    "korean":          CAT["Korean"],
    "thai":            CAT["Thai"],
    "indian":          CAT["Indian"],
    "italian":         CAT["Italian"],
    "pizza":           CAT["Pizza"],
    "coffee":          CAT["Coffee"],
    "breakfast":       CAT["Breakfast"],
    "burger":          CAT["American"],
    "seafood":         CAT["Seafood"],
    "bbq":             CAT["BBQ"],
    "mediterranean":   CAT["Mediterranean"],
    "sushi":           CAT["Japanese"],
    "vietnamese":      CAT["Restaurant"],
    "other":           CAT["Other"],
}

# Name keyword → category (last resort)
NAME_KEYWORDS: list[tuple[str, str]] = [
    ("pizza",        CAT["Pizza"]),
    ("sushi",        CAT["Japanese"]),
    ("ramen",        CAT["Japanese"]),
    ("pho",          CAT["Restaurant"]),
    ("taco",         CAT["Mexican"]),
    ("burrito",      CAT["Mexican"]),
    ("chinese",      CAT["Chinese"]),
    ("thai",         CAT["Thai"]),
    ("indian",       CAT["Indian"]),
    ("mediterranean",CAT["Mediterranean"]),
    ("korean",       CAT["Korean"]),
    ("italian",      CAT["Italian"]),
    ("coffee",       CAT["Coffee"]),
    ("starbucks",    CAT["Coffee"]),
    ("cafe",         CAT["Cafe"]),
    ("bakery",       CAT["Breakfast"]),
    ("boba",         CAT["Coffee"]),
    ("tea",          CAT["Coffee"]),
    ("bar ",         CAT["Bar"]),
    ("brewery",      CAT["Bar"]),
    ("burger",       CAT["American"]),
    ("bbq",          CAT["BBQ"]),
    ("seafood",      CAT["Seafood"]),
    ("dessert",      CAT["Desserts"]),
    ("ice cream",    CAT["Desserts"]),
    ("donut",        CAT["Desserts"]),
    ("breakfast",    CAT["Breakfast"]),
    ("diner",        CAT["American"]),
    ("grill",        CAT["American"]),
    ("steakhouse",   CAT["American"]),
    ("steak",        CAT["American"]),
    ("sandwich",     CAT["Restaurant"]),
    ("sub ",         CAT["Restaurant"]),
    ("wings",        CAT["American"]),
    ("fried chicken",CAT["American"]),
    ("noodle",       CAT["Restaurant"]),
    ("dim sum",      CAT["Chinese"]),
]


def _resolve_category(
    category_hint: Optional[str],
    raw_payload: Optional[str],
    name: Optional[str],
) -> Optional[str]:
    """Return best category_id or None if unresolvable."""

    # Parse OSM tags
    osm_cuisine = None
    osm_amenity = None

    if raw_payload:
        try:
            rp = raw_payload if isinstance(raw_payload, dict) else json.loads(raw_payload)
            if isinstance(rp, str):
                rp = json.loads(rp)
            tags = rp.get("tags", {}) if isinstance(rp, dict) else {}
            osm_cuisine = str(tags.get("cuisine", "")).lower().strip()
            osm_amenity = str(tags.get("amenity", "")).lower().strip()
        except Exception:
            pass

    # Priority 1: OSM cuisine (specific)
    if osm_cuisine:
        for key, cat_id in CUISINE_MAP.items():
            if key in osm_cuisine:
                return cat_id

    # Priority 2: OSM amenity (general)
    if osm_amenity:
        cat_id = AMENITY_MAP.get(osm_amenity)
        if cat_id:
            return cat_id

    # Priority 3: category_hint
    if category_hint:
        hint_norm = category_hint.lower().strip().replace("_", " ")
        cat_id = HINT_MAP.get(category_hint.lower().strip())
        if cat_id:
            return cat_id
        # partial match
        for key, cat_id in HINT_MAP.items():
            if key in hint_norm:
                return cat_id

    # Priority 4: name keywords
    if name:
        name_lower = name.lower()
        for keyword, cat_id in NAME_KEYWORDS:
            if keyword in name_lower:
                return cat_id

    return None


def run_backfill() -> None:
    db = SessionLocal()
    try:
        # Baseline
        total = db.execute(text(
            "SELECT COUNT(*) FROM places WHERE is_active = 1"
        )).scalar()
        with_cat = db.execute(text(
            "SELECT COUNT(DISTINCT place_id) FROM place_categories"
        )).scalar()
        logger.info("baseline: total=%s with_category=%s pct=%.1f%%",
                    total, with_cat, (with_cat / total * 100) if total else 0.0)

        # Get places needing categories: no category OR only "Other"
        # Use a CTE to find eligible place_ids
        eligible_query = text("""
            SELECT DISTINCT p.id as place_id
            FROM places p
            WHERE p.is_active = 1
            AND p.id NOT IN (
                SELECT DISTINCT pc.place_id
                FROM place_categories pc
                WHERE pc.category_id != :other_id
            )
        """)
        eligible_ids = {
            row[0]
            for row in db.execute(eligible_query, {"other_id": OTHER_ID}).fetchall()
        }
        logger.info("eligible_places (no cat or only Other): %s", len(eligible_ids))

        # Fetch best candidate signals for each eligible place
        # Get ALL candidates for eligible places, ordered: prefer OSM (has tags), then any
        candidates_query = text("""
            SELECT
                dc.resolved_place_id,
                dc.category_hint,
                dc.raw_payload,
                p.name,
                dc.source
            FROM discovery_candidates dc
            JOIN places p ON p.id = dc.resolved_place_id
            WHERE dc.resolved_place_id IS NOT NULL
            AND dc.resolved_place_id IN (
                SELECT DISTINCT p2.id FROM places p2 WHERE p2.is_active = 1
                AND p2.id NOT IN (
                    SELECT DISTINCT pc.place_id FROM place_categories pc
                    WHERE pc.category_id != :other_id
                )
            )
            ORDER BY dc.source DESC, dc.created_at DESC
        """)
        rows = db.execute(candidates_query, {"other_id": OTHER_ID}).fetchall()
        logger.info("candidate signals to process: %s", len(rows))

        # Build best category per place_id (first hit wins per priority)
        place_category: dict[str, str] = {}
        for place_id, hint, raw_payload, name, source in rows:
            if place_id in place_category:
                # Already have a good one — only override if it's Other
                existing = place_category[place_id]
                if existing != OTHER_ID:
                    continue

            cat_id = _resolve_category(hint, raw_payload, name)
            if cat_id:
                place_category[place_id] = cat_id

        logger.info("place_category resolved: %s", len(place_category))

        # Count resolved vs unresolved
        resolved_good = sum(1 for v in place_category.values() if v != OTHER_ID)
        resolved_other = sum(1 for v in place_category.values() if v == OTHER_ID)
        logger.info("resolved_to_specific=%s resolved_to_other=%s", resolved_good, resolved_other)

        # Apply: remove existing Other entries, insert new category
        inserted = 0
        updated = 0
        BATCH = 500

        items = list(place_category.items())
        for i in range(0, len(items), BATCH):
            batch = items[i:i + BATCH]
            for place_id, cat_id in batch:
                # Remove existing Other category for this place
                db.execute(text(
                    "DELETE FROM place_categories WHERE place_id = :pid AND category_id = :cid"
                ), {"pid": place_id, "cid": OTHER_ID})

                # Check if this category already exists
                exists = db.execute(text(
                    "SELECT 1 FROM place_categories WHERE place_id = :pid AND category_id = :cid"
                ), {"pid": place_id, "cid": cat_id}).fetchone()

                if not exists:
                    db.execute(text(
                        "INSERT INTO place_categories (place_id, category_id) VALUES (:pid, :cid)"
                    ), {"pid": place_id, "cid": cat_id})
                    inserted += 1
                else:
                    updated += 1

            db.commit()
            logger.info("progress: processed=%s inserted=%s updated=%s", i + len(batch), inserted, updated)

        logger.info("backfill_done: inserted=%s updated=%s", inserted, updated)

        # Final metrics
        with_cat_after = db.execute(text(
            "SELECT COUNT(DISTINCT place_id) FROM place_categories"
        )).scalar()
        other_after = db.execute(text(
            "SELECT COUNT(DISTINCT place_id) FROM place_categories WHERE category_id = :cid AND place_id NOT IN (SELECT place_id FROM place_categories WHERE category_id != :cid)"
        ), {"cid": OTHER_ID}).scalar()
        logger.info("after: with_category=%s pct=%.1f%% only_other=%s",
                    with_cat_after, (with_cat_after / total * 100) if total else 0.0, other_after)

    finally:
        db.close()


if __name__ == "__main__":
    run_backfill()
