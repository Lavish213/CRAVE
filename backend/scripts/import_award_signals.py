"""
import_award_signals.py

Bootstrap award signals from static JSON data (Michelin, Eater, James Beard).
Matches by exact name (case-insensitive) + city_id. Fuzzy matches logged for review.

Usage:
    python scripts/import_award_signals.py            # live run
    python scripts/import_award_signals.py --dry-run  # count only
    python scripts/import_award_signals.py --fuzzy-threshold 85  # adjust fuzzy cutoff

Signal values by award tier:
    michelin_star   → 1.0
    michelin_bib    → 0.80
    james_beard     → 0.90
    eater_heatmap   → 0.60
    eater_38        → 0.70
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_signal import PlaceSignal
from app.db.models.city import city_uuid

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False


# ---------------------------------------------------------------------------
# AWARD DATA — edit this dict to add new awards
# ---------------------------------------------------------------------------

AWARD_TIER_VALUES = {
    "michelin_star":  1.0,
    "michelin_bib":   0.80,
    "james_beard":    0.90,
    "eater_38":       0.70,
    "eater_heatmap":  0.60,
}

AWARDS: list[dict] = [
    # Format: {"place_name": str, "city_id": str, "award_type": str, "year": int}

    # ── OAKLAND · Michelin Bay Area 2024 ────────────────────────────────────────
    {"place_name": "Commis",                        "city_id": "oakland",  "award_type": "michelin_star", "year": 2024},
    {"place_name": "Homeroom",                      "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Soba Ichi",                     "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Tacos Oscar",                   "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Vientian Cafe",                 "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Tigerlily Berkeley",            "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    # Michelin Bib — DB-confirmed Oakland restaurants
    {"place_name": "Pizzaiolo",                     "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Cholita Linda",                 "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Ramen Shop",                    "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Hawking Bird",                  "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "FOB Kitchen",                   "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Itani Ramen",                   "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Shawarmaji",                    "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Wahpepah's Kitchen",            "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Phnom Penh",                    "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Breads of India",               "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Shan Dong Restaurant",          "city_id": "oakland",  "award_type": "michelin_bib",  "year": 2024},
    # ── OAKLAND · Eater 38 / Heatmap ────────────────────────────────────────────
    {"place_name": "Sobre Mesa",                    "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Sobre Mesa",                    "city_id": "oakland",  "award_type": "eater_38",      "year": 2024},
    {"place_name": "Horn Barbecue",                 "city_id": "oakland",  "award_type": "eater_38",      "year": 2024},
    {"place_name": "Pizzaiolo",                     "city_id": "oakland",  "award_type": "eater_38",      "year": 2024},
    {"place_name": "Cholita Linda",                 "city_id": "oakland",  "award_type": "eater_38",      "year": 2024},
    {"place_name": "Ramen Shop",                    "city_id": "oakland",  "award_type": "eater_38",      "year": 2024},
    {"place_name": "FOB Kitchen",                   "city_id": "oakland",  "award_type": "eater_38",      "year": 2024},
    {"place_name": "Hawking Bird",                  "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Belotti",                       "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Kiraku",                        "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Boichik Bagels",                "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Oori",                          "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Marufuku Ramen",                "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Calavera",                      "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Kingston 11 Cuisine",           "city_id": "oakland",  "award_type": "eater_38",      "year": 2023},
    {"place_name": "Sliver Pizzeria",               "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2023},
    {"place_name": "Xolo Taqueria",                 "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Drexl",                         "city_id": "oakland",  "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "alaMar Dominican Kitchen and Bar","city_id":"oakland", "award_type": "eater_38",      "year": 2024},
    # ── OAKLAND · James Beard ────────────────────────────────────────────────────
    {"place_name": "Commis",                        "city_id": "oakland",  "award_type": "james_beard",   "year": 2024},
    {"place_name": "Horn Barbecue",                 "city_id": "oakland",  "award_type": "james_beard",   "year": 2023},
    {"place_name": "Pizzaiolo",                     "city_id": "oakland",  "award_type": "james_beard",   "year": 2023},
    {"place_name": "Wahpepah's Kitchen",            "city_id": "oakland",  "award_type": "james_beard",   "year": 2024},
    {"place_name": "FOB Kitchen",                   "city_id": "oakland",  "award_type": "james_beard",   "year": 2023},
    {"place_name": "Lois the Pie Queen",            "city_id": "oakland",  "award_type": "james_beard",   "year": 2023},

    # ── BERKELEY · Michelin Bay Area 2024 ───────────────────────────────────────
    {"place_name": "Chez Panisse",                  "city_id": "berkeley", "award_type": "michelin_star", "year": 2024},
    {"place_name": "Zut!",                          "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "La Marcha",                     "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Cafe Raj",                      "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Comal",                         "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    # Michelin Bib — DB-confirmed Berkeley restaurants
    {"place_name": "Gather",                        "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Ippuku",                        "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Revival Kitchen",               "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Tacubaya",                      "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Kirala",                        "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Cheeseboard Pizza",             "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Agrodolce",                     "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    {"place_name": "Great China",                   "city_id": "berkeley", "award_type": "michelin_bib",  "year": 2024},
    # ── BERKELEY · Eater 38 / Heatmap ───────────────────────────────────────────
    {"place_name": "Chez Panisse",                  "city_id": "berkeley", "award_type": "eater_38",      "year": 2024},
    {"place_name": "Comal",                         "city_id": "berkeley", "award_type": "eater_38",      "year": 2024},
    {"place_name": "Cheeseboard Pizza",             "city_id": "berkeley", "award_type": "eater_38",      "year": 2024},
    {"place_name": "Gather",                        "city_id": "berkeley", "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Revival Kitchen",               "city_id": "berkeley", "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Ippuku",                        "city_id": "berkeley", "award_type": "eater_heatmap", "year": 2024},
    {"place_name": "Angeline's Louisiana Kitchen",  "city_id": "berkeley", "award_type": "eater_38",      "year": 2023},
    {"place_name": "Great China",                   "city_id": "berkeley", "award_type": "eater_38",      "year": 2024},
    {"place_name": "Tacubaya",                      "city_id": "berkeley", "award_type": "eater_heatmap", "year": 2024},
    # ── BERKELEY · James Beard ───────────────────────────────────────────────────
    {"place_name": "Chez Panisse",                  "city_id": "berkeley", "award_type": "james_beard",   "year": 2024},
    {"place_name": "Gather",                        "city_id": "berkeley", "award_type": "james_beard",   "year": 2023},
    {"place_name": "Revival Kitchen",               "city_id": "berkeley", "award_type": "james_beard",   "year": 2023},
]


def _load_place_map(db) -> dict[tuple[str, str], str]:
    """Returns {(city_id, name_lower): place_id} for all active places."""
    rows = db.execute(
        select(Place.id, Place.name, Place.city_id)
        .where(Place.is_active.is_(True))
    ).fetchall()
    return {(row.city_id, row.name.strip().lower()): row.id for row in rows}


def _external_event_id(award: dict) -> str:
    safe_name = award["place_name"].lower().replace(" ", "_")[:40]
    return f"award_{award['award_type']}_{safe_name}_{award['year']}"


def run(dry_run: bool = False, fuzzy_threshold: int = 88) -> None:
    db = SessionLocal()
    place_map = _load_place_map(db)
    print(f"Active places loaded: {len(place_map)}")

    matched: list[tuple[str, dict]] = []   # (place_id, award)
    fuzzy_candidates: list[dict] = []
    unmatched: list[dict] = []

    for award in AWARDS:
        # award["city_id"] is a slug like "oakland" — resolve to UUID
        city_id = city_uuid(award["city_id"])
        name_lower = award["place_name"].strip().lower()
        key = (city_id, name_lower)

        if key in place_map:
            matched.append((place_map[key], award))
            continue

        # Fuzzy match within same city
        if HAS_RAPIDFUZZ:
            best_score = 0
            best_key = None
            for (cid, nlower), pid in place_map.items():
                if cid != city_id:
                    continue
                score = fuzz.ratio(name_lower, nlower)
                if score > best_score:
                    best_score = score
                    best_key = (cid, nlower)

            if best_score >= fuzzy_threshold and best_key:
                fuzzy_candidates.append({
                    "award": award,
                    "matched_name": best_key[1],
                    "score": best_score,
                    "place_id": place_map[best_key],
                })
                continue

        unmatched.append(award)

    print(f"\nExact matches: {len(matched)}")
    print(f"Fuzzy candidates (threshold={fuzzy_threshold}): {len(fuzzy_candidates)}")
    print(f"Unmatched: {len(unmatched)}")

    if fuzzy_candidates:
        print("\nFuzzy matches (review before including):")
        for fc in fuzzy_candidates:
            print(f"  [{fc['score']:.0f}] '{fc['award']['place_name']}' → '{fc['matched_name']}'")

    if unmatched:
        print("\nUnmatched awards (no place found):")
        for a in unmatched:
            print(f"  {a['city_id']}: '{a['place_name']}' ({a['award_type']} {a['year']})")

    if dry_run:
        print("\nDRY RUN — no writes")
        return

    inserted = 0
    skipped = 0

    for place_id, award in matched:
        value = AWARD_TIER_VALUES.get(award["award_type"], 0.5)
        ext_id = _external_event_id(award)

        # Check for existing signal (idempotent)
        existing = db.execute(
            select(PlaceSignal.id)
            .where(
                PlaceSignal.place_id == place_id,
                PlaceSignal.provider == "editorial",
                PlaceSignal.signal_type == "award",
                PlaceSignal.external_event_id == ext_id,
            )
        ).first()

        if existing:
            skipped += 1
            continue

        signal = PlaceSignal(
            place_id=place_id,
            provider="editorial",
            signal_type="award",
            value=value,
            raw_value=f"{award['award_type']}:{award['year']}",
            external_event_id=ext_id,
        )
        db.add(signal)
        inserted += 1

    db.commit()
    db.close()
    print(f"\nInserted {inserted} award signals ({skipped} already existed)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--fuzzy-threshold", type=int, default=88)
    args = parser.parse_args()
    run(dry_run=args.dry_run, fuzzy_threshold=args.fuzzy_threshold)
