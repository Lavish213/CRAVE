"""
reconcile_dc_websites.py

Populates Place.website for active places that have no website,
using matching DiscoveryCandidate records that DO have a website from OSM.

Matching strategy:
  1. Same city_id
  2. Exact name match (case-insensitive, stripped)
  3. DC has a non-empty, validated website
  4. Place has no website currently

Safe: reads DC, writes only Place.website. No duplication.
Idempotent: re-running skips already-populated places.

Usage:
    python scripts/reconcile_dc_websites.py            # live run
    python scripts/reconcile_dc_websites.py --dry-run  # count only
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update
from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.discovery_candidate import DiscoveryCandidate

# URLs from these domains are delivery/chain directories — not useful as canonical website
_SKIP_DOMAINS = {
    "grubhub.com", "doordash.com", "ubereats.com", "order.online",
    "disneyland.disney.go.com", "disneylandresort.com",
    "traderjoes.com",  # chain locator, not canonical
}


def _is_valid_website(url: str) -> bool:
    if not url or len(url) < 8:
        return False
    # Reject concatenated URLs (OSM data sometimes has two URLs joined)
    second_http = url.find("http", 4)
    if second_http != -1:
        return False
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        netloc = parsed.netloc.lower().lstrip("www.")
        for skip in _SKIP_DOMAINS:
            if netloc == skip or netloc.endswith("." + skip):
                return False
        return bool(parsed.netloc)
    except Exception:
        return False


def run(dry_run: bool = False) -> None:
    db = SessionLocal()

    # Load active places with no website, keyed by (city_id, name_lower)
    place_rows = db.execute(
        select(Place.id, Place.name, Place.city_id)
        .where(
            Place.is_active.is_(True),
            (Place.website.is_(None)) | (Place.website == ""),
        )
    ).fetchall()

    place_map: dict[tuple[str, str], str] = {}
    for row in place_rows:
        key = (row.city_id, row.name.strip().lower())
        place_map[key] = row.id

    print(f"Active places with no website: {len(place_map)}")

    # Load DC records with websites, same city scope
    dc_rows = db.execute(
        select(DiscoveryCandidate.name, DiscoveryCandidate.city_id, DiscoveryCandidate.website)
        .where(
            DiscoveryCandidate.website.isnot(None),
            DiscoveryCandidate.website != "",
            DiscoveryCandidate.city_id.in_([k[0] for k in place_map]),
        )
    ).fetchall()

    print(f"DC records with website in matching cities: {len(dc_rows)}")

    matched: dict[str, str] = {}  # place_id -> website

    for dc in dc_rows:
        key = (dc.city_id, dc.name.strip().lower())
        if key not in place_map:
            continue
        place_id = place_map[key]
        if place_id in matched:
            continue  # already have a match
        website = (dc.website or "").strip()
        if not _is_valid_website(website):
            continue
        matched[place_id] = website

    print(f"Matched places to populate: {len(matched)}")

    if dry_run:
        print("DRY RUN — no writes")
        for pid, url in list(matched.items())[:10]:
            print(f"  {pid}: {url[:80]}")
        return

    updated = 0
    for place_id, website in matched.items():
        db.execute(
            update(Place)
            .where(Place.id == place_id)
            .values(website=website[:255])
        )
        updated += 1

    db.commit()
    db.close()
    print(f"Updated {updated} places with website from DC records")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
