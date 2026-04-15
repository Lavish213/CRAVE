"""
import_osm_candidates.py

Seeds the discovery_candidates table from legacy OSM-processed JSON files.

Usage:
    python scripts/import_osm_candidates.py            # live import
    python scripts/import_osm_candidates.py --dry-run  # count only, no writes
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
import uuid

# Allow running from repo root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, func

from app.db.session import SessionLocal
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.db.models.city import City, city_uuid

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DATA_DIR = "/Users/angelowashington/Downloads/food-1 4/backend/data/processed/"
BATCH_SIZE = 500
CONFIDENCE = 0.35
SOURCE = "generic"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def extract_slug(filename: str) -> str:
    """
    Convert filename to a city slug.

    Examples:
        san-francisco_v1.json          -> san-francisco
        oakland_places_with_images.json -> oakland
        normalized_places.json          -> normalized-places  (skipped later)
    """
    base = os.path.basename(filename)
    slug = base
    for suffix in ("_places_with_images.json", "_v1.json", ".json"):
        if slug.endswith(suffix):
            slug = slug[: -len(suffix)]
            break
    return slug.replace("_", "-")


def extract_places(data) -> list[dict]:
    """Return the list of place dicts regardless of top-level format."""
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if "places" in data:
            return data["places"]
        # Single-place dict — unlikely, but handle gracefully
        if "name" in data:
            return [data]
    return []


def should_skip(place: dict) -> tuple[bool, str]:
    """Return (True, reason) if the record should be excluded."""
    if not isinstance(place, dict):
        return True, "no_name"
    name = place.get("name") or ""
    if not str(name).strip():
        return True, "no_name"
    place["name"] = str(name).strip()  # normalize in-place for later use
    lat = place.get("lat")
    lng = place.get("lng")
    if lat is None or lng is None:
        return True, "no_coords"
    try:
        float(lat)
        float(lng)
    except (TypeError, ValueError):
        return True, "bad_coords"
    category = (place.get("category") or "").strip().lower()
    if category == "unknown":
        return True, "unknown_category"
    return False, ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(dry_run: bool = False) -> None:
    files = sorted(glob.glob(os.path.join(DATA_DIR, "*.json")))
    if not files:
        print(f"ERROR: no JSON files found in {DATA_DIR}")
        sys.exit(1)

    print(f"Found {len(files)} JSON files")

    db = SessionLocal()

    # Pre-load all cities into a slug -> id map
    city_rows = db.execute(select(City.slug, City.id)).fetchall()
    city_map: dict[str, str] = {row.slug: row.id for row in city_rows}
    print(f"Loaded {len(city_map)} cities from DB")

    # Pre-load existing external_ids to avoid duplicates (source=generic)
    existing_ext = set(
        db.execute(
            select(DiscoveryCandidate.external_id).where(
                DiscoveryCandidate.source == SOURCE,
                DiscoveryCandidate.external_id.isnot(None),
            )
        ).scalars().all()
    )
    print(f"Pre-loaded {len(existing_ext)} existing external_ids for source='{SOURCE}'")

    # Pre-load existing (city_id, name) pairs to prevent UNIQUE constraint failures on re-run
    existing_name_city: set[tuple[str, str]] = set(
        db.execute(
            select(DiscoveryCandidate.city_id, DiscoveryCandidate.name).where(
                DiscoveryCandidate.source == SOURCE,
            )
        ).fetchall()
    )
    # Normalize to lowercase for comparison
    existing_name_city_lower: set[tuple[str, str]] = {
        (cid, n.lower()) for cid, n in existing_name_city
    }
    print(f"Pre-loaded {len(existing_name_city_lower)} existing name+city pairs")

    # Counters
    total_records = 0
    skipped_no_name = 0
    skipped_no_coords = 0
    skipped_bad_coords = 0
    skipped_unknown_cat = 0
    skipped_no_city = 0
    skipped_duplicate = 0
    will_import = 0

    batch: list[DiscoveryCandidate] = []
    committed_batches = 0

    # Track (city_id, name) pairs seen this run — pre-seeded with DB state to prevent re-run collisions
    seen_name_city: set[tuple[str, str]] = set(existing_name_city_lower)
    # Track external_ids seen this run — pre-seeded with DB state
    seen_ext_ids: set[str] = set(existing_ext)

    for filepath in files:
        slug = extract_slug(filepath)

        # Skip the empty normalized_places.json
        if slug == "normalized-places":
            print(f"  Skipping {os.path.basename(filepath)} (empty/not a city file)")
            continue

        # Resolve city
        city_id = city_map.get(slug)
        if city_id is None:
            # Try deterministic UUID lookup as fallback
            det_id = city_uuid(slug)
            det_check = db.execute(
                select(City.id).where(City.id == det_id)
            ).scalar_one_or_none()
            if det_check:
                city_id = det_check
                city_map[slug] = city_id

        with open(filepath, encoding="utf-8") as fh:
            try:
                raw = json.load(fh)
            except json.JSONDecodeError as exc:
                print(f"  WARN: could not parse {os.path.basename(filepath)}: {exc}")
                continue

        places = extract_places(raw)
        file_count = 0
        file_imported = 0

        for place in places:
            total_records += 1
            file_count += 1

            skip, reason = should_skip(place)
            if skip:
                if reason == "no_name":
                    skipped_no_name += 1
                elif reason == "no_coords":
                    skipped_no_coords += 1
                elif reason == "bad_coords":
                    skipped_bad_coords += 1
                elif reason == "unknown_category":
                    skipped_unknown_cat += 1
                continue

            if city_id is None:
                skipped_no_city += 1
                continue

            # Build a stable external_id string
            raw_id = str(place.get("id", "")).strip()
            ext_id = f"{slug}:{raw_id}" if raw_id else None

            # Duplicate check: external_id (seen_ext_ids is pre-seeded from DB)
            if ext_id and ext_id in seen_ext_ids:
                skipped_duplicate += 1
                continue

            # Duplicate check: name + city_id combo (in-run dedup)
            name_key = (city_id, place["name"].strip().lower())
            if name_key in seen_name_city:
                skipped_duplicate += 1
                continue

            will_import += 1
            file_imported += 1

            if ext_id:
                seen_ext_ids.add(ext_id)
            seen_name_city.add(name_key)

            if not dry_run:
                candidate = DiscoveryCandidate(
                    id=str(uuid.uuid4()),
                    name=place["name"].strip()[:160],
                    lat=float(place["lat"]),
                    lng=float(place["lng"]),
                    city_id=city_id,
                    source=SOURCE,
                    external_id=ext_id[:120] if ext_id else None,
                    website=(place.get("external_url") or "")[:255] or None,
                    category_hint=(place.get("category") or "")[:80] or None,
                    confidence_score=CONFIDENCE,
                    status="raw",
                    resolved=False,
                    blocked=False,
                )
                batch.append(candidate)

                if len(batch) >= BATCH_SIZE:
                    db.add_all(batch)
                    db.commit()
                    committed_batches += 1
                    print(
                        f"  Committed batch {committed_batches} "
                        f"({committed_batches * BATCH_SIZE} records so far)"
                    )
                    batch = []

        print(
            f"  {os.path.basename(filepath)}: {file_count} records, "
            f"{file_imported} to import, city_id={city_id or 'MISSING'}"
        )

    # Final batch
    if not dry_run and batch:
        db.add_all(batch)
        db.commit()
        print(f"  Committed final batch ({len(batch)} records)")

    db.close()

    # ---------------------------------------------------------------------------
    # Summary
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print(f"{'DRY RUN SUMMARY' if dry_run else 'IMPORT COMPLETE'}")
    print("=" * 60)
    print(f"  Total records scanned  : {total_records}")
    print(f"  Skipped (no name)      : {skipped_no_name}")
    print(f"  Skipped (no coords)    : {skipped_no_coords}")
    print(f"  Skipped (bad coords)   : {skipped_bad_coords}")
    print(f"  Skipped (unknown cat)  : {skipped_unknown_cat}")
    print(f"  Skipped (no city)      : {skipped_no_city}")
    print(f"  Skipped (duplicate)    : {skipped_duplicate}")
    print(f"  {'Would import' if dry_run else 'Imported'}       : {will_import}")
    print("=" * 60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import OSM candidates into CRAVE DB")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Count records that WOULD be imported without writing anything",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run)
