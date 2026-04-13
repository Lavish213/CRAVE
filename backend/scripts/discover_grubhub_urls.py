#!/usr/bin/env python3
"""
discover_grubhub_urls.py
========================
Search Grubhub by restaurant name + coordinates to find matching
Grubhub pages for seeded places, then set grubhub_url on the place.

Uses the authenticated Grubhub search API with existing cookies.

Usage
-----
    # Dry-run (shows matches without writing to DB):
    python backend/scripts/discover_grubhub_urls.py --dry-run --limit 50

    # Write matches to DB:
    python backend/scripts/discover_grubhub_urls.py --limit 200

    # Resume from a specific city slug:
    python backend/scripts/discover_grubhub_urls.py --city stockton

    # Full run (all cities, all places):
    python backend/scripts/discover_grubhub_urls.py

Notes
-----
- Skips places that already have grubhub_url set.
- Only writes grubhub_url if name similarity >= 0.65 AND distance < 0.8 km.
- Sleeps 0.8s between Grubhub search calls to avoid rate limiting.
- Cookies expire; re-run grab_grubhub_cookies.py if you see 401 errors.
"""
from __future__ import annotations

import argparse
import difflib
import logging
import math
import os
import sys
import time
from pathlib import Path
from typing import Optional

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Load .grubhub_env
_env_file = ROOT_DIR / "backend" / ".grubhub_env"
if _env_file.exists():
    with open(_env_file) as f:
        for line in f:
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if "=" in line and not line.startswith("#"):
                k, _, v = line.partition("=")
                k = k.strip()
                v = v.strip().strip("'\"")
                if k and k not in os.environ:
                    os.environ[k] = v

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)

GRUBHUB_SEARCH_URL = "https://api-gtm.grubhub.com/restaurants/search"
GRUBHUB_RESTAURANT_BASE = "https://www.grubhub.com/restaurant"

NAME_SIMILARITY_THRESHOLD = 0.65   # minimum fuzzy match ratio
MAX_DISTANCE_KM = 0.8               # maximum distance for a valid match
SLEEP_BETWEEN_REQUESTS = 0.8        # seconds


# ─────────────────────────────────────────────────────────────────────────────
# GEO UTILS
# ─────────────────────────────────────────────────────────────────────────────

def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlng / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def name_similarity(a: str, b: str) -> float:
    a = a.lower().strip()
    b = b.lower().strip()
    return difflib.SequenceMatcher(None, a, b).ratio()


# ─────────────────────────────────────────────────────────────────────────────
# GRUBHUB SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def _build_session():
    from app.services.menu.fetchers.grubhub_fetcher import (
        _load_grubhub_cookies,
        _load_perimeter_x,
    )
    from curl_cffi import requests as cffi_requests

    cookies = _load_grubhub_cookies()
    px = _load_perimeter_x()

    session = cffi_requests.Session(impersonate="chrome110")
    session.cookies.update(cookies)

    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://www.grubhub.com",
        "Referer": "https://www.grubhub.com/",
    }
    if px:
        headers["perimeter-x"] = px

    return session, headers


def search_grubhub(
    session,
    headers: dict,
    name: str,
    lat: float,
    lng: float,
    page_size: int = 5,
) -> list[dict]:
    """Search Grubhub for a restaurant by name + location.

    Uses PICKUP mode so lat/lng is treated as the restaurant's own
    coordinates (not a customer delivery address). This gives much
    higher match rates for location-based discovery.
    """
    try:
        resp = session.get(
            GRUBHUB_SEARCH_URL,
            params={
                "orderMethod": "pickup",
                "locationMode": "PICKUP",
                "facetSet": "umamiV2",
                "pageSize": page_size,
                "hideHateos": "true",
                "latitude": lat,
                "longitude": lng,
                "radius": 2,
                "platform": "WEB",
                "restaurantName": name,
            },
            headers=headers,
            timeout=12,
        )
        if resp.status_code == 401:
            print("\nFATAL: 401 Unauthorized — cookies expired. Re-run grab_grubhub_cookies.py", flush=True)
            sys.exit(1)
        if resp.status_code != 200:
            logger.warning("search_failed name=%s status=%s", name, resp.status_code)
            return []

        data = resp.json()
        return data.get("search_result", {}).get("results", []) or []

    except Exception as e:
        logger.warning("search_exception name=%s error=%s", name, e)
        return []


def find_best_match(
    results: list[dict],
    place_name: str,
    lat: float,
    lng: float,
) -> Optional[dict]:
    """
    Find the best matching Grubhub result for a place.
    Returns the result dict if match is good enough, else None.
    """
    best = None
    best_score = 0.0

    for r in results:
        r_name = r.get("name", "")
        r_lat = r.get("address", {}).get("latitude")
        r_lng = r.get("address", {}).get("longitude")

        sim = name_similarity(place_name, r_name)
        if sim < NAME_SIMILARITY_THRESHOLD:
            continue

        dist_km = float("inf")
        if r_lat and r_lng:
            try:
                dist_km = haversine_km(lat, lng, float(r_lat), float(r_lng))
            except Exception:
                pass

        if dist_km > MAX_DISTANCE_KM:
            continue

        # Score: weighted combination of name similarity + proximity
        score = sim * 0.7 + max(0, 1 - dist_km / MAX_DISTANCE_KM) * 0.3

        if score > best_score:
            best_score = score
            best = r

    return best


def build_grubhub_url(result: dict) -> Optional[str]:
    rid = result.get("restaurant_id", "")
    slug = result.get("merchant_url_path", "")
    if not rid:
        return None
    if slug:
        return f"{GRUBHUB_RESTAURANT_BASE}/{slug}/{rid}"
    return f"{GRUBHUB_RESTAURANT_BASE}/{rid}"


# ─────────────────────────────────────────────────────────────────────────────
# MAIN DISCOVERY LOOP
# ─────────────────────────────────────────────────────────────────────────────

def run(
    limit: int = 0,
    city_slug: Optional[str] = None,
    dry_run: bool = False,
    skip_has_menu: bool = True,
) -> None:
    from app.db.session import SessionLocal
    from app.db.models.place import Place

    db = SessionLocal()

    try:
        query = db.query(Place).filter(
            Place.is_active.is_(True),
            Place.grubhub_url.is_(None),
            Place.lat.isnot(None),
            Place.lng.isnot(None),
        )

        if city_slug:
            from app.db.models.city import City
            city = db.query(City).filter(City.slug == city_slug).first()
            if not city:
                print(f"ERROR: city not found: {city_slug}", flush=True)
                sys.exit(1)
            query = query.filter(Place.city_id == city.id)

        if skip_has_menu:
            query = query.filter(Place.has_menu.is_(False))

        if limit:
            query = query.limit(limit)

        places = query.all()

    finally:
        db.close()

    total = len(places)
    print(f"\n{'DRY RUN - ' if dry_run else ''}Discovering Grubhub URLs for {total} places", flush=True)
    print("=" * 65, flush=True)

    if not places:
        print("No eligible places found.", flush=True)
        return

    session, headers = _build_session()

    matched = 0
    skipped = 0
    failed = 0

    for i, place in enumerate(places, 1):
        name = place.name or ""
        lat = place.lat
        lng = place.lng

        if not name or lat is None or lng is None:
            skipped += 1
            continue

        results = search_grubhub(session, headers, name, lat, lng)
        best = find_best_match(results, name, lat, lng) if results else None

        if best:
            grubhub_url = build_grubhub_url(best)
            sim = name_similarity(name, best.get("name", ""))
            r_lat = best.get("address", {}).get("latitude")
            r_lng = best.get("address", {}).get("longitude")
            dist = haversine_km(lat, lng, float(r_lat), float(r_lng)) if r_lat and r_lng else None

            print(
                f"[{i}/{total}] MATCH  {name!r}\n"
                f"         → {best.get('name')!r}  sim={sim:.2f}  "
                f"{'dist='+f'{dist:.3f}km' if dist is not None else 'dist=?'}\n"
                f"         → {grubhub_url}",
                flush=True,
            )

            if not dry_run:
                db2 = SessionLocal()
                try:
                    fresh = db2.get(Place, place.id)
                    if fresh and not fresh.grubhub_url:
                        fresh.grubhub_url = grubhub_url
                        db2.commit()
                        matched += 1
                except Exception as e:
                    db2.rollback()
                    logger.warning("write_failed place=%s error=%s", place.id, e)
                    failed += 1
                finally:
                    db2.close()
            else:
                matched += 1
        else:
            print(f"[{i}/{total}] NO MATCH  {name!r}  lat={lat:.4f} lng={lng:.4f}", flush=True)
            skipped += 1

        # Progress every 50
        if i % 50 == 0:
            print(
                f"\n--- Progress: {i}/{total}  matched={matched}  skipped={skipped}  failed={failed} ---\n",
                flush=True,
            )

        time.sleep(SLEEP_BETWEEN_REQUESTS)

    print("\n" + "=" * 65, flush=True)
    print("DISCOVERY COMPLETE", flush=True)
    print(f"  total_searched:  {total}", flush=True)
    print(f"  matched:         {matched}", flush=True)
    print(f"  no_match/skip:   {skipped}", flush=True)
    print(f"  write_errors:    {failed}", flush=True)
    if not dry_run:
        print(f"\n  grubhub_url set on {matched} places — ready for menu enrichment.", flush=True)
    else:
        print(f"\n  DRY RUN — no changes written.", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Discover Grubhub URLs for seeded places")
    parser.add_argument("--limit", type=int, default=0, help="Max places to process (0=all)")
    parser.add_argument("--city", default=None, help="Filter by city slug (e.g. stockton)")
    parser.add_argument("--dry-run", action="store_true", help="Show matches without writing to DB")
    parser.add_argument("--include-has-menu", action="store_true", help="Also process places with has_menu=True")
    args = parser.parse_args()

    run(
        limit=args.limit,
        city_slug=args.city,
        dry_run=args.dry_run,
        skip_has_menu=not args.include_has_menu,
    )


if __name__ == "__main__":
    main()
