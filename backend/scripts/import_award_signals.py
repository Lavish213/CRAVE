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
    # Bay Area Michelin 2024
    {"place_name": "Commis",                  "city_id": "oakland",   "award_type": "michelin_star",  "year": 2024},
    {"place_name": "Adega",                   "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Boot & Shoe Service",      "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Camins 2 Dreams",          "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Dyafa",                    "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Homeroom",                 "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Mago",                     "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Miss Ollie's",             "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Nyum Bai",                 "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Soba Ichi",                "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Tacos Oscar",              "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Telefèric Barcelona",      "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Tigerlily Patisserie",     "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Vientian Cafe",            "city_id": "oakland",   "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Zut!",                     "city_id": "berkeley",  "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Chez Panisse",             "city_id": "berkeley",  "award_type": "michelin_star",  "year": 2024},
    {"place_name": "La Marcha",                "city_id": "berkeley",  "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Raj's",                    "city_id": "berkeley",  "award_type": "michelin_bib",   "year": 2024},
    {"place_name": "Comal",                    "city_id": "berkeley",  "award_type": "michelin_bib",   "year": 2024},
    # Eater SF Heatmap 2024 — Oakland/Berkeley
    {"place_name": "Daytrip",                  "city_id": "oakland",   "award_type": "eater_heatmap",  "year": 2024},
    {"place_name": "Noodle in a Haystack",     "city_id": "oakland",   "award_type": "eater_heatmap",  "year": 2024},
    {"place_name": "Sobre Mesa",               "city_id": "oakland",   "award_type": "eater_heatmap",  "year": 2024},
    {"place_name": "Sobre Mesa",               "city_id": "oakland",   "award_type": "eater_38",       "year": 2024},
    {"place_name": "Nyum Bai",                 "city_id": "oakland",   "award_type": "eater_38",       "year": 2024},
    {"place_name": "Camins 2 Dreams",          "city_id": "oakland",   "award_type": "eater_38",       "year": 2024},
    {"place_name": "Daytrip",                  "city_id": "oakland",   "award_type": "eater_38",       "year": 2024},
    {"place_name": "Altta",                    "city_id": "oakland",   "award_type": "eater_heatmap",  "year": 2024},
    {"place_name": "Horn Barbecue",            "city_id": "oakland",   "award_type": "eater_38",       "year": 2024},
    {"place_name": "Tacos El Patron",          "city_id": "oakland",   "award_type": "eater_heatmap",  "year": 2024},
    # James Beard nominees / winners
    {"place_name": "Chez Panisse",             "city_id": "berkeley",  "award_type": "james_beard",    "year": 2024},
    {"place_name": "Commis",                   "city_id": "oakland",   "award_type": "james_beard",    "year": 2024},
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
