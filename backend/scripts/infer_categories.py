"""
infer_categories.py — Enhanced Category Backfill

Fixes the 64% of places that have no specific category.

Coverage:
  - Places with 0 categories
  - Places with ONLY generic categories (Restaurant, Bar, Other, Others, Restaurants, Bars)

Signal priority per place:
  1. discovery_candidates OSM cuisine tag
  2. discovery_candidates OSM amenity tag
  3. discovery_candidates category_hint
  4. Place name keyword inference
  5. rank_score heuristic (high-rank restaurant → Fine Dining)

Run:
  cd /Users/angelowashington/CRAVE/backend
  python3 -m scripts.infer_categories [--dry-run] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import logging
from typing import Optional

from sqlalchemy import text

from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

# ── Category ID map ────────────────────────────────────────────────────────────

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
    "Restaurant":    "660b5eae-cf5e-5e15-8ae6-5b5c66199d6e",
    "Cafe":          "8d2f5e7a-00f2-56ea-8ad5-17b00e8549ce",
    "Bar":           "76fc27fe-b407-5d2c-b330-b5194b678730",
    "Fine Dining":   "59c91ed1-628c-50db-8345-3938e5faf090",
    "Fast Casual":   "fd6c57eb-c3f8-59b0-b533-c42237412e28",
    "Other":         "97ee17ef-a9ac-5079-8527-4448c07f1c23",
    "Vegan":         "58f5a0b2-99fd-5fa6-a8db-a8b21eacd5f8",
}

# Generic category IDs — places with ONLY these get re-inferred
_GENERIC_IDS = frozenset({
    CAT["Restaurant"],
    CAT["Other"],
    "660b5eae-cf5e-5e15-8ae6-5b5c66199d6e",  # Restaurant (redundant safety)
    "97ee17ef-a9ac-5079-8527-4448c07f1c23",   # Other
})

# We'll also detect Bar as "generic" only when it's the SOLE category
_BAR_ID = CAT["Bar"]

# ── OSM cuisine → category ─────────────────────────────────────────────────────

CUISINE_MAP: dict[str, str] = {
    "mexican": CAT["Mexican"], "tex-mex": CAT["Mexican"],
    "italian": CAT["Italian"], "pizza": CAT["Pizza"],
    "chinese": CAT["Chinese"], "dim_sum": CAT["Chinese"],
    "japanese": CAT["Japanese"], "sushi": CAT["Japanese"],
    "ramen": CAT["Japanese"], "udon": CAT["Japanese"],
    "korean": CAT["Korean"],
    "thai": CAT["Thai"],
    "indian": CAT["Indian"],
    "mediterranean": CAT["Mediterranean"], "greek": CAT["Mediterranean"],
    "lebanese": CAT["Mediterranean"], "turkish": CAT["Mediterranean"],
    "falafel": CAT["Mediterranean"],
    "american": CAT["American"], "burger": CAT["American"],
    "chicken": CAT["American"], "wings": CAT["American"],
    "bbq": CAT["BBQ"], "barbecue": CAT["BBQ"],
    "seafood": CAT["Seafood"], "fish": CAT["Seafood"],
    "breakfast": CAT["Breakfast"], "brunch": CAT["Breakfast"],
    "coffee_shop": CAT["Coffee"], "coffee": CAT["Coffee"],
    "bubble_tea": CAT["Coffee"], "tea": CAT["Coffee"],
    "ice_cream": CAT["Desserts"], "frozen_yogurt": CAT["Desserts"],
    "donut": CAT["Desserts"], "dessert": CAT["Desserts"],
    "cake": CAT["Desserts"], "pastry": CAT["Desserts"],
    "french": CAT["Fine Dining"],
    "vietnamese": CAT["Restaurant"],
    "filipino": CAT["Restaurant"],
    "sandwich": CAT["Restaurant"],
    "vegan": CAT["Vegan"], "vegetarian": CAT["Vegan"],
    "juice": CAT["Cafe"], "cafe": CAT["Cafe"],
    "bakery": CAT["Cafe"],
}

AMENITY_MAP: dict[str, str] = {
    "fast_food": CAT["Fast Casual"],
    "cafe": CAT["Cafe"],
    "coffee_shop": CAT["Coffee"],
    "bar": CAT["Bar"],
    "pub": CAT["Bar"],
    "biergarten": CAT["Bar"],
    "ice_cream": CAT["Desserts"],
    "confectionery": CAT["Desserts"],
    "bakery": CAT["Cafe"],
}

HINT_MAP: dict[str, str] = {
    "fast_food": CAT["Fast Casual"], "fast food": CAT["Fast Casual"],
    "cafe": CAT["Cafe"], "bakery": CAT["Cafe"],
    "bar": CAT["Bar"], "pub": CAT["Bar"],
    "dessert": CAT["Desserts"], "ice_cream": CAT["Desserts"],
    "american": CAT["American"], "mexican": CAT["Mexican"],
    "chinese": CAT["Chinese"], "japanese": CAT["Japanese"],
    "korean": CAT["Korean"], "thai": CAT["Thai"],
    "indian": CAT["Indian"], "italian": CAT["Italian"],
    "pizza": CAT["Pizza"], "coffee": CAT["Coffee"],
    "breakfast": CAT["Breakfast"], "brunch": CAT["Breakfast"],
    "burger": CAT["American"], "seafood": CAT["Seafood"],
    "bbq": CAT["BBQ"], "mediterranean": CAT["Mediterranean"],
    "sushi": CAT["Japanese"], "vegan": CAT["Vegan"],
}

# ── Name keyword inference (ordered: more specific first) ─────────────────────

NAME_KEYWORDS: list[tuple[str, str]] = [
    # Fine dining markers
    ("omakase",         CAT["Japanese"]),
    ("kaiseki",         CAT["Japanese"]),
    ("izakaya",         CAT["Japanese"]),
    ("kappo",           CAT["Japanese"]),
    # Cuisine in name
    ("sushi",           CAT["Japanese"]),
    ("ramen",           CAT["Japanese"]),
    ("udon",            CAT["Japanese"]),
    ("soba",            CAT["Japanese"]),
    ("yakitori",        CAT["Japanese"]),
    ("tonkatsu",        CAT["Japanese"]),
    ("tempura",         CAT["Japanese"]),
    ("japanese",        CAT["Japanese"]),
    ("japan",           CAT["Japanese"]),
    ("taco",            CAT["Mexican"]),
    ("burrito",         CAT["Mexican"]),
    ("tamale",          CAT["Mexican"]),
    ("quesadilla",      CAT["Mexican"]),
    ("tlayuda",         CAT["Mexican"]),
    ("mexican",         CAT["Mexican"]),
    ("taqueria",        CAT["Mexican"]),
    ("taquieria",       CAT["Mexican"]),
    ("pho",             CAT["Restaurant"]),  # Vietnamese but we don't have that cat
    ("banh mi",         CAT["Restaurant"]),
    ("dim sum",         CAT["Chinese"]),
    ("dumpling",        CAT["Chinese"]),
    ("chinese",         CAT["Chinese"]),
    ("china",           CAT["Chinese"]),
    ("szechuan",        CAT["Chinese"]),
    ("sichuan",         CAT["Chinese"]),
    ("cantonese",       CAT["Chinese"]),
    ("taiwanese",       CAT["Chinese"]),
    ("hong kong",       CAT["Chinese"]),
    ("korean",          CAT["Korean"]),
    ("bibimbap",        CAT["Korean"]),
    ("bulgogi",         CAT["Korean"]),
    ("thai",            CAT["Thai"]),
    ("indian",          CAT["Indian"]),
    ("curry",           CAT["Indian"]),
    ("masala",          CAT["Indian"]),
    ("tandoor",         CAT["Indian"]),
    ("dosa",            CAT["Indian"]),
    ("mediterranean",   CAT["Mediterranean"]),
    ("greek",           CAT["Mediterranean"]),
    ("falafel",         CAT["Mediterranean"]),
    ("shawarma",        CAT["Mediterranean"]),
    ("hummus",          CAT["Mediterranean"]),
    ("kebab",           CAT["Mediterranean"]),
    ("pita",            CAT["Mediterranean"]),
    ("lebanese",        CAT["Mediterranean"]),
    ("persian",         CAT["Mediterranean"]),
    ("pizza",           CAT["Pizza"]),
    ("pizzeria",        CAT["Pizza"]),
    ("pizz",            CAT["Pizza"]),
    ("pasta",           CAT["Italian"]),
    ("italian",         CAT["Italian"]),
    ("trattoria",       CAT["Italian"]),
    ("osteria",         CAT["Italian"]),
    ("ristorante",      CAT["Italian"]),
    ("gelato",          CAT["Italian"]),
    ("bbq",             CAT["BBQ"]),
    ("barbecue",        CAT["BBQ"]),
    ("smokehouse",      CAT["BBQ"]),
    ("smoke",           CAT["BBQ"]),     # Smoking pig etc
    ("smoked",          CAT["BBQ"]),
    ("seafood",         CAT["Seafood"]),
    ("oyster",          CAT["Seafood"]),
    ("crab",            CAT["Seafood"]),
    ("lobster",         CAT["Seafood"]),
    ("fish",            CAT["Seafood"]),
    ("shrimp",          CAT["Seafood"]),
    ("vegan",           CAT["Vegan"]),
    ("vegetarian",      CAT["Vegan"]),
    ("plant",           CAT["Vegan"]),
    # Bakery/desserts (before cafe/coffee to be more specific)
    ("bakery",          CAT["Cafe"]),
    ("boulangerie",     CAT["Cafe"]),
    ("patisserie",      CAT["Desserts"]),
    ("bake shop",       CAT["Desserts"]),
    ("bake",            CAT["Cafe"]),
    ("pastry",          CAT["Desserts"]),
    ("creamery",        CAT["Desserts"]),
    ("creperie",        CAT["Desserts"]),
    ("ice cream",       CAT["Desserts"]),
    ("gelato",          CAT["Desserts"]),
    ("donut",           CAT["Desserts"]),
    ("doughnut",        CAT["Desserts"]),
    ("cupcake",         CAT["Desserts"]),
    ("dessert",         CAT["Desserts"]),
    ("macaron",         CAT["Desserts"]),
    ("chocolat",        CAT["Desserts"]),
    ("chocolate",       CAT["Desserts"]),
    ("confection",      CAT["Desserts"]),
    # Coffee/tea
    ("coffee",          CAT["Coffee"]),
    ("espresso",        CAT["Coffee"]),
    ("roaster",         CAT["Coffee"]),
    ("roastery",        CAT["Coffee"]),
    ("starbucks",       CAT["Coffee"]),
    ("peet's",          CAT["Coffee"]),
    ("boba",            CAT["Coffee"]),
    ("bubble tea",      CAT["Coffee"]),
    ("tea house",       CAT["Coffee"]),
    # Cafe
    ("cafe",            CAT["Cafe"]),
    ("café",            CAT["Cafe"]),
    ("coffee house",    CAT["Cafe"]),
    # Breakfast
    ("breakfast",       CAT["Breakfast"]),
    ("brunch",          CAT["Breakfast"]),
    ("waffle",          CAT["Breakfast"]),
    ("pancake",         CAT["Breakfast"]),
    ("diner",           CAT["American"]),
    ("egg",             CAT["Breakfast"]),  # Egg shop, egg place
    # American
    ("burger",          CAT["American"]),
    ("grill",           CAT["American"]),
    ("steakhouse",      CAT["American"]),
    ("steak house",     CAT["American"]),
    ("steak",           CAT["American"]),
    ("wings",           CAT["American"]),
    ("fried chicken",   CAT["American"]),
    ("american",        CAT["American"]),
    ("sandwich",        CAT["American"]),
    ("deli",            CAT["American"]),
    ("sub ",            CAT["American"]),
    ("hoagie",          CAT["American"]),
    ("hot dog",         CAT["American"]),
    ("mac and cheese",  CAT["American"]),
    ("mac & cheese",    CAT["American"]),
    ("soul food",       CAT["American"]),
    # Bar
    ("brewery",         CAT["Bar"]),
    ("brewpub",         CAT["Bar"]),
    ("taproom",         CAT["Bar"]),
    ("tavern",          CAT["Bar"]),
    ("pub ",            CAT["Bar"]),
    (" bar",            CAT["Bar"]),
    ("bar ",            CAT["Bar"]),
    ("lounge",          CAT["Bar"]),
    ("cocktail",        CAT["Bar"]),
    ("wine bar",        CAT["Bar"]),
    # Fast casual
    ("chipotle",        CAT["Fast Casual"]),
    ("subway",          CAT["Fast Casual"]),
    ("mcdonald",        CAT["Fast Casual"]),
    ("wendy",           CAT["Fast Casual"]),
    ("taco bell",       CAT["Fast Casual"]),
    ("jack in the box", CAT["Fast Casual"]),
    ("panda express",   CAT["Fast Casual"]),
]

# ── High-rank restaurant heuristic threshold ──────────────────────────────────
# When no keyword matches: rank>=0.38 Restaurant-only places → Fine Dining
_FINE_DINING_MIN_RANK = 0.38


def _resolve_from_signals(hint: Optional[str], raw_payload: Optional[str]) -> Optional[str]:
    osm_cuisine = osm_amenity = None
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

    if osm_cuisine:
        for key, cat_id in CUISINE_MAP.items():
            if key in osm_cuisine:
                return cat_id

    if osm_amenity:
        cat_id = AMENITY_MAP.get(osm_amenity)
        if cat_id and cat_id not in _GENERIC_IDS:
            return cat_id

    if hint:
        hint_norm = hint.lower().strip()
        cat_id = HINT_MAP.get(hint_norm)
        if cat_id and cat_id not in _GENERIC_IDS:
            return cat_id
        for key, cat_id in HINT_MAP.items():
            if key in hint_norm and cat_id not in _GENERIC_IDS:
                return cat_id

    return None


def _resolve_from_name(name: str) -> Optional[str]:
    if not name:
        return None
    name_lower = name.lower()
    for keyword, cat_id in NAME_KEYWORDS:
        if keyword in name_lower:
            return cat_id
    return None


def run(dry_run: bool = False, limit: Optional[int] = None) -> None:
    db = SessionLocal()
    try:
        # ── Baseline ───────────────────────────────────────────────────────────
        total = db.execute(text("SELECT COUNT(*) FROM places WHERE is_active = 1")).scalar()

        before_specific = db.execute(text("""
            SELECT COUNT(DISTINCT p.id) FROM places p
            JOIN place_categories pc ON p.id = pc.place_id
            JOIN categories c ON pc.category_id = c.id
            WHERE p.is_active = 1
            AND LOWER(c.name) NOT IN ('restaurant','restaurants','bar','bars','other','others','')
        """)).scalar()
        logger.info("baseline: total=%s with_specific_cat=%s (%.1f%%)",
                    total, before_specific, before_specific / total * 100 if total else 0)

        # ── Eligible places: only generic categories ───────────────────────────
        eligible_rows = db.execute(text("""
            SELECT p.id, p.name, p.rank_score
            FROM places p
            WHERE p.is_active = 1
            GROUP BY p.id
            HAVING p.id NOT IN (
                SELECT DISTINCT pc.place_id
                FROM place_categories pc
                JOIN categories c ON pc.category_id = c.id
                WHERE LOWER(c.name) NOT IN ('restaurant','restaurants','bar','bars','other','others','')
            )
            ORDER BY p.rank_score DESC
        """ + (f" LIMIT {limit}" if limit else ""))).fetchall()

        logger.info("eligible_places: %s", len(eligible_rows))

        # ── Load discovery_candidate signals ──────────────────────────────────
        dc_signals: dict[str, list[tuple]] = {}
        if eligible_rows:
            ids_csv = ",".join(f"'{r[0]}'" for r in eligible_rows)
            dc_rows = db.execute(text(f"""
                SELECT dc.resolved_place_id, dc.category_hint, dc.raw_payload, dc.source
                FROM discovery_candidates dc
                WHERE dc.resolved_place_id IN ({ids_csv})
                ORDER BY dc.source DESC, dc.created_at DESC
            """)).fetchall()
            for place_id, hint, raw, source in dc_rows:
                dc_signals.setdefault(place_id, []).append((hint, raw, source))

        logger.info("places_with_dc_signals: %s", len(dc_signals))

        # ── Resolve category per place ─────────────────────────────────────────
        assignments: list[tuple[str, str]] = []  # (place_id, cat_id)

        for place_id, name, rank_score in eligible_rows:
            cat_id: Optional[str] = None

            # Priority 1: discovery_candidates signals
            for hint, raw, source in dc_signals.get(place_id, []):
                cat_id = _resolve_from_signals(hint, raw)
                if cat_id and cat_id not in _GENERIC_IDS:
                    break

            # Priority 2: name keyword
            if not cat_id or cat_id in _GENERIC_IDS:
                name_cat = _resolve_from_name(name or "")
                if name_cat and name_cat not in _GENERIC_IDS:
                    cat_id = name_cat

            # Priority 3: high-rank restaurant heuristic → Fine Dining
            if not cat_id or cat_id in _GENERIC_IDS:
                if (rank_score or 0) >= _FINE_DINING_MIN_RANK:
                    cat_id = CAT["Fine Dining"]

            if cat_id and cat_id not in _GENERIC_IDS:
                assignments.append((place_id, cat_id))

        logger.info("assignments_resolved: %s / %s (%.1f%%)",
                    len(assignments), len(eligible_rows),
                    len(assignments) / len(eligible_rows) * 100 if eligible_rows else 0)

        if dry_run:
            # Print sample
            cat_name_map = {v: k for k, v in CAT.items()}
            for place_id, cat_id in assignments[:30]:
                name = next((r[1] for r in eligible_rows if r[0] == place_id), "?")
                logger.info("  DRY_RUN: %s → %s", name, cat_name_map.get(cat_id, cat_id))
            logger.info("DRY_RUN — no changes written.")
            return

        # ── Write assignments ──────────────────────────────────────────────────
        GENERIC_ID_LIST = list(_GENERIC_IDS)
        inserted = skipped = 0
        BATCH = 500

        for i in range(0, len(assignments), BATCH):
            batch = assignments[i:i + BATCH]
            for place_id, cat_id in batch:
                # Don't duplicate
                exists = db.execute(text("""
                    SELECT 1 FROM place_categories WHERE place_id = :pid AND category_id = :cid
                """), {"pid": place_id, "cid": cat_id}).fetchone()

                if not exists:
                    db.execute(text("""
                        INSERT INTO place_categories (place_id, category_id) VALUES (:pid, :cid)
                    """), {"pid": place_id, "cid": cat_id})
                    inserted += 1
                else:
                    skipped += 1

            db.commit()
            if (i // BATCH) % 5 == 0:
                logger.info("progress: %s/%s inserted=%s skipped=%s",
                            i + len(batch), len(assignments), inserted, skipped)

        logger.info("write_done: inserted=%s skipped=%s", inserted, skipped)

        # ── Final metrics ──────────────────────────────────────────────────────
        after_specific = db.execute(text("""
            SELECT COUNT(DISTINCT p.id) FROM places p
            JOIN place_categories pc ON p.id = pc.place_id
            JOIN categories c ON pc.category_id = c.id
            WHERE p.is_active = 1
            AND LOWER(c.name) NOT IN ('restaurant','restaurants','bar','bars','other','others','')
        """)).scalar()

        logger.info("after: with_specific_cat=%s (%.1f%%)  delta=+%s",
                    after_specific, after_specific / total * 100 if total else 0,
                    after_specific - before_specific)

    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit)
