"""
targeted_enrichment.py

Targeted enrichment for high-signal broken elites:
  - Adds verified real websites to award-holding or notable places
  - Adds missed award signals for name-variant matches
  - Only writes to places explicitly named here — no bulk operations

All websites manually verified. None are Yelp, aggregators, or delivery links.

Usage:
    python scripts/targeted_enrichment.py --dry-run
    python scripts/targeted_enrichment.py
"""
from __future__ import annotations

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_signal import PlaceSignal
from app.db.models.city import city_uuid


# ---------------------------------------------------------------------------
# VERIFIED WEBSITE ENRICHMENTS
# Format: (place_name_exact, city_slug, verified_website)
# ---------------------------------------------------------------------------

WEBSITE_ENRICHMENTS = [
    # Michelin star — no website in DB
    ("Commis",               "oakland",  "https://www.commisrestaurant.com"),
    # Michelin Bib Gourmand
    ("Soba Ichi",            "oakland",  "https://sobaichi.com"),
    # Eater SF 38 / notable Oakland BBQ
    ("Horn Barbecue",        "oakland",  "https://hornbbq.com"),
    # Eater SF 38 / Afro-Colombian Oakland
    ("Sobre Mesa",           "oakland",  "https://www.sobremesaoakland.com"),
    # Well-known Berkeley Italian; two locations (SF + Oakland area)
    ("A16",                  "berkeley", "https://a16pizza.com"),
    # Berkeley non-profit coffee; refugees employment
    ("1951 Coffee Company",  "berkeley", "https://1951coffee.com"),
    # Kirala Japanese restaurant group Berkeley
    ("Kirala 2",             "berkeley", "https://kirala.com"),
]


# ---------------------------------------------------------------------------
# MISSED AWARD SIGNALS (name variant matches not caught by exact import)
# Format: (place_name_exact, city_slug, award_type, year, value)
# ---------------------------------------------------------------------------

MISSED_AWARDS = [
    # "Tigerlily Patisserie" in Michelin — stored in OSM as "Tigerlily Berkeley"
    ("Tigerlily Berkeley",   "oakland",  "michelin_bib",  2024,  0.80),
    # "Raj's" in Michelin — stored in DB as "Cafe Raj"
    ("Cafe Raj",             "berkeley", "michelin_bib",  2024,  0.80),
]

AWARD_TIER_VALUES = {
    "michelin_star": 1.0,
    "michelin_bib":  0.80,
    "james_beard":   0.90,
    "eater_38":      0.70,
    "eater_heatmap": 0.60,
}


def run(dry_run: bool = False) -> None:
    db = SessionLocal()

    website_updates = []
    website_skipped = []
    award_inserts = []
    award_skipped = []

    # -----------------------------------------------------------------------
    # WEBSITE ENRICHMENTS
    # -----------------------------------------------------------------------
    for place_name, city_slug, website in WEBSITE_ENRICHMENTS:
        cid = city_uuid(city_slug)
        row = db.execute(
            select(Place.id, Place.name, Place.website, Place.rank_score)
            .where(Place.name == place_name, Place.city_id == cid, Place.is_active.is_(True))
        ).first()

        if not row:
            print(f"  MISS  {place_name!r} in {city_slug}")
            continue

        if row.website:
            website_skipped.append((row.name, row.website))
            print(f"  SKIP  {row.name!r} already has website: {row.website}")
            continue

        website_updates.append((row.id, row.name, row.rank_score, website))
        print(f"  ADD   {row.rank_score:.4f}  {row.name!r} → {website}")

    # -----------------------------------------------------------------------
    # MISSED AWARD SIGNALS
    # -----------------------------------------------------------------------
    print()
    for place_name, city_slug, award_type, year, value in MISSED_AWARDS:
        cid = city_uuid(city_slug)
        row = db.execute(
            select(Place.id, Place.name, Place.rank_score)
            .where(Place.name == place_name, Place.city_id == cid, Place.is_active.is_(True))
        ).first()

        if not row:
            print(f"  MISS  award target {place_name!r} in {city_slug}")
            continue

        safe_name = place_name.lower().replace(" ", "_")[:40]
        ext_id = f"award_{award_type}_{safe_name}_{year}"

        existing = db.execute(
            select(PlaceSignal.id)
            .where(PlaceSignal.place_id == row.id, PlaceSignal.external_event_id == ext_id)
        ).first()

        if existing:
            award_skipped.append(row.name)
            print(f"  SKIP  award already exists for {row.name!r}")
            continue

        award_inserts.append((row.id, row.name, row.rank_score, award_type, year, value, ext_id))
        print(f"  ADD   award {award_type}({value:.2f})  {row.rank_score:.4f} → {row.name!r}")

    print()
    print(f"Website updates:  {len(website_updates)} (skipped {len(website_skipped)})")
    print(f"Award inserts:    {len(award_inserts)} (skipped {len(award_skipped)})")

    if dry_run:
        print("\nDRY RUN — no writes")
        return

    # Write websites
    for place_id, name, _, website in website_updates:
        db.execute(update(Place).where(Place.id == place_id).values(website=website[:255]))

    # Write award signals
    for place_id, name, _, award_type, year, value, ext_id in award_inserts:
        signal = PlaceSignal(
            place_id=place_id,
            provider="editorial",
            signal_type="award",
            value=value,
            raw_value=f"{award_type}:{year}",
            external_event_id=ext_id,
        )
        db.add(signal)

    db.commit()
    db.close()
    print(f"\nWrote {len(website_updates)} website updates and {len(award_inserts)} award signals")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
