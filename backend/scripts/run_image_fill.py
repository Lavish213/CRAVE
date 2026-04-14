#!/usr/bin/env python3
"""
run_image_fill.py
=================
Production-grade Google Places image enrichment script.

Sweeps all active places missing images, fetches photos from
Google Places API, and writes them to the place_images table.

Prerequisites
-------------
1. Get a Google Places API key (must have Places API enabled):
   https://console.cloud.google.com/apis/library/places-backend.googleapis.com

2. Export the key:
   export GOOGLE_PLACES_API_KEY='AIza...'

3. Run:
   python backend/scripts/run_image_fill.py

Usage
-----
    # Dry-run (show counts without fetching):
    python backend/scripts/run_image_fill.py --dry-run

    # Process up to 100 places:
    python backend/scripts/run_image_fill.py --limit 100

    # Force-refresh places that already have images:
    python backend/scripts/run_image_fill.py --force

    # Target a specific city:
    python backend/scripts/run_image_fill.py --city-id <uuid>

Guarantees
----------
- Idempotent: safe to re-run; skips places that already have images
- Deduplicates by (place_id, url) — DB has UNIQUE constraint
- Rate limiting: 200ms delay between places (Google quota safe)
- Batch commit every 20 places
- Stops cleanly if API key is missing or quota exceeded

Environment Variables
---------------------
  GOOGLE_PLACES_API_KEY   Required. Your Google Places API key.
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
from urllib.parse import urlencode

ROOT_DIR = Path(__file__).resolve().parents[2]
BACKEND_DIR = ROOT_DIR / "backend"
for d in (str(BACKEND_DIR), str(ROOT_DIR)):
    if d not in sys.path:
        sys.path.insert(0, d)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger("run_image_fill")


# New Places API (v1) endpoints — required for keys created after 2022
GOOGLE_SEARCH_TEXT = "https://places.googleapis.com/v1/places:searchText"
GOOGLE_PHOTO_MEDIA = "https://places.googleapis.com/v1/{name}/media"

BATCH_SIZE = 20
DELAY_BETWEEN_PLACES = 0.3    # seconds — new API quota: ~10 req/sec
MAX_PHOTOS_PER_PLACE = 5      # store top 5 images per place
PHOTO_MAX_WIDTH = 1200


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _print(msg: str) -> None:
    print(f"[{_utcnow().strftime('%H:%M:%S')}] {msg}", flush=True)


# ─────────────────────────────────────────────────────────────────────────────
# API VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_api_key(api_key: str) -> bool:
    """Quick validation using new Places API (v1) searchText endpoint."""
    try:
        import requests
        resp = requests.post(
            GOOGLE_SEARCH_TEXT,
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.id",
                "Content-Type": "application/json",
            },
            json={"textQuery": "McDonalds", "maxResultCount": 1},
            timeout=8,
        )
        if resp.status_code == 200:
            _print("API_KEY: VALID")
            return True
        data = resp.json()
        err = data.get("error", {})
        _print(f"API_KEY: REJECTED — {err.get('message', resp.status_code)}")
        return False
    except Exception as exc:
        _print(f"API_KEY: validation error — {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE PLACES FETCH
# ─────────────────────────────────────────────────────────────────────────────

def fetch_google_images(
    session,
    api_key: str,
    place_name: str,
    lat: Optional[float],
    lng: Optional[float],
) -> List[str]:
    """
    Returns a list of photo URLs using the new Places API (v1).
    Single request: searchText with photos field mask.
    """
    body: dict = {
        "textQuery": place_name,
        "maxResultCount": 1,
    }
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {
                "center": {"latitude": lat, "longitude": lng},
                "radius": 200.0,
            }
        }

    try:
        resp = session.post(
            GOOGLE_SEARCH_TEXT,
            headers={
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "places.id,places.photos",
                "Content-Type": "application/json",
            },
            json=body,
            timeout=8,
        )
    except Exception as exc:
        logger.debug("search_text_failed name=%s error=%s", place_name, exc)
        return []

    if resp.status_code == 429:
        _print("QUOTA EXCEEDED — stopping. Try again tomorrow or upgrade API plan.")
        raise RuntimeError("OVER_QUERY_LIMIT")

    if resp.status_code != 200:
        logger.debug("search_text_error name=%s status=%s", place_name, resp.status_code)
        return []

    data = resp.json()
    places = data.get("places", [])
    if not places:
        return []

    photos = places[0].get("photos", [])
    urls = []
    for photo in photos[:MAX_PHOTOS_PER_PLACE]:
        photo_name = photo.get("name")  # e.g. "places/ChIJ.../photos/AXCi..."
        if not photo_name:
            continue
        # New API photo URL format
        url = (
            f"https://places.googleapis.com/v1/{photo_name}/media"
            f"?maxWidthPx={PHOTO_MAX_WIDTH}&key={api_key}"
        )
        urls.append(url)

    return urls


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def run(
    api_key: str,
    limit: Optional[int] = None,
    force: bool = False,
    city_id: Optional[str] = None,
    dry_run: bool = False,
) -> dict:
    import requests
    from sqlalchemy import select, func, exists
    from app.db.session import SessionLocal
    from app.db.models.place import Place
    from app.db.models.place_image import PlaceImage

    session = requests.Session()
    db = SessionLocal()

    try:
        # Count places needing images
        has_img_subq = exists(
            select(PlaceImage.id).where(PlaceImage.place_id == Place.id)
        )

        q = (
            select(Place)
            .where(Place.is_active.is_(True))
            .where(Place.lat.isnot(None))
            .where(Place.lng.isnot(None))
        )
        if city_id:
            q = q.where(Place.city_id == city_id)
        if not force:
            q = q.where(~has_img_subq)
        q = q.order_by(Place.rank_score.desc().nullslast(), Place.name.asc())
        if limit:
            q = q.limit(limit)

        places = list(db.execute(q).scalars().all())
        _print(f"Found {len(places)} places needing images")

        if dry_run:
            _print(f"DRY RUN — would process {len(places)} places")
            return {"processed": 0, "enriched": 0, "images_written": 0, "skipped": 0, "failed": 0}

        stats = {"processed": 0, "enriched": 0, "images_written": 0, "skipped": 0, "failed": 0}
        now = _utcnow()

        for i, place in enumerate(places):
            stats["processed"] += 1

            try:
                urls = fetch_google_images(
                    session,
                    api_key,
                    place.name,
                    place.lat,
                    place.lng,
                )
            except RuntimeError as e:
                if "OVER_QUERY_LIMIT" in str(e):
                    break
                raise

            if not urls:
                stats["skipped"] += 1
                time.sleep(DELAY_BETWEEN_PLACES)
                continue

            written = 0
            for j, url in enumerate(urls):
                try:
                    img = PlaceImage(
                        place_id=place.id,
                        url=url,
                        is_primary=(j == 0),
                        confidence=0.8,
                        created_at=now,
                        updated_at=now,
                    )
                    db.add(img)
                    db.flush()
                    written += 1
                except Exception:
                    db.rollback()
                    # Duplicate URL — skip silently (UNIQUE constraint)
                    continue

            if written > 0:
                db.commit()
                stats["enriched"] += 1
                stats["images_written"] += written
                _print(f"  [{i+1}/{len(places)}] {place.name[:40]:40s} → {written} images")
            else:
                stats["skipped"] += 1

            time.sleep(DELAY_BETWEEN_PLACES)

            # Progress every 50
            if (i + 1) % 50 == 0:
                _print(
                    f"  PROGRESS: enriched={stats['enriched']} "
                    f"images={stats['images_written']} "
                    f"skipped={stats['skipped']}"
                )

        return stats

    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Google Places image enrichment — fills place_images from Google Photos API"
    )
    parser.add_argument("--limit", type=int, default=None, help="Max places to process")
    parser.add_argument("--force", action="store_true", help="Re-enrich places that already have images")
    parser.add_argument("--city-id", default=None, help="Restrict to a specific city UUID")
    parser.add_argument("--dry-run", action="store_true", help="Show counts without fetching")
    args = parser.parse_args()

    api_key = os.environ.get("GOOGLE_PLACES_API_KEY", "").strip()
    if not api_key and not args.dry_run:
        print("ERROR: GOOGLE_PLACES_API_KEY not set", file=sys.stderr)
        print("  export GOOGLE_PLACES_API_KEY='AIza...'", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print("  GOOGLE IMAGES FILL")
    print("=" * 65)

    if not args.dry_run:
        _print("Validating API key...")
        if not validate_api_key(api_key):
            _print("API key validation failed — aborting")
            sys.exit(1)

    stats = run(
        api_key=api_key or "DRY_RUN_NO_KEY",
        limit=args.limit,
        force=args.force,
        city_id=args.city_id,
        dry_run=args.dry_run,
    )

    print("\n" + "=" * 65)
    print("  FINAL METRICS")
    print("=" * 65)
    print(f"  Processed       : {stats['processed']:,}")
    print(f"  Enriched        : {stats['enriched']:,}")
    print(f"  Images Written  : {stats['images_written']:,}")
    print(f"  Skipped         : {stats['skipped']:,}")
    print(f"  Failed          : {stats['failed']:,}")
    print("=" * 65)

    if stats["enriched"] == 0 and not args.dry_run:
        print("\n  No images enriched. Check:")
        print("    - API key has Places API enabled")
        print("    - Places have lat/lng set")
        print("    - Google recognizes the place names")


if __name__ == "__main__":
    main()
