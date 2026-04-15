"""
sweep_social_urls.py

Scans DiscoveryCandidate.website for social platform URLs (Instagram, TikTok, YouTube,
Linktree). For each DC that matches an active Place (exact name + city_id), creates a
PlaceSignal(type='creator') using the platform's confidence value.

Also updates Place.website with the social URL if the place has no website yet.

Confidence values (from social extractor specs):
    tiktok    → 0.40
    instagram → 0.35
    youtube   → 0.30
    linktree  → 0.25  (indirect — actual platform unknown)

Safe: idempotent via external_event_id. Re-running is harmless.

Usage:
    python scripts/sweep_social_urls.py            # live run
    python scripts/sweep_social_urls.py --dry-run  # count only
"""
from __future__ import annotations

import argparse
import os
import sys
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select
from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.place_signal import PlaceSignal
from app.db.models.discovery_candidate import DiscoveryCandidate


_SOCIAL_PLATFORMS = {
    "instagram.com":  ("instagram", 0.35),
    "tiktok.com":     ("tiktok",    0.40),
    "youtube.com":    ("youtube",   0.30),
    "youtu.be":       ("youtube",   0.30),
    "linktr.ee":      ("linktree",  0.25),
    "linktree.com":   ("linktree",  0.25),
    "beacons.ai":     ("linktree",  0.25),
    "lnk.bio":        ("linktree",  0.25),
}


def _detect_social(url: str) -> tuple[str, float] | None:
    """Returns (platform, confidence) if the URL is a social platform, else None."""
    if not url:
        return None
    try:
        netloc = urlparse(url).netloc.lower().lstrip("www.")
        for domain, (platform, confidence) in _SOCIAL_PLATFORMS.items():
            if netloc == domain or netloc.endswith("." + domain):
                return platform, confidence
    except Exception:
        pass
    return None


def run(dry_run: bool = False) -> None:
    db = SessionLocal()

    # Build place map: (city_id, name_lower) -> (place_id, current_website)
    place_rows = db.execute(
        select(Place.id, Place.name, Place.city_id, Place.website)
        .where(Place.is_active.is_(True))
    ).fetchall()

    place_map: dict[tuple[str, str], tuple[str, str | None]] = {}
    for row in place_rows:
        key = (row.city_id, row.name.strip().lower())
        place_map[key] = (row.id, row.website)

    print(f"Active places: {len(place_map)}")

    # Fetch DC records with websites containing social domain keywords
    # Use LIKE for broad pre-filter, then precise domain check in Python
    dc_rows = db.execute(
        select(DiscoveryCandidate.name, DiscoveryCandidate.city_id, DiscoveryCandidate.website)
        .where(
            DiscoveryCandidate.website.isnot(None),
            DiscoveryCandidate.website != "",
            DiscoveryCandidate.city_id.in_([k[0] for k in place_map]),
        )
    ).fetchall()

    print(f"DC records with website in matching cities: {len(dc_rows)}")

    signals_to_create: list[dict] = []

    for dc in dc_rows:
        url = (dc.website or "").strip()
        social = _detect_social(url)
        if not social:
            continue

        platform, confidence = social
        key = (dc.city_id, dc.name.strip().lower())
        if key not in place_map:
            continue

        place_id, current_website = place_map[key]
        safe_url = url[:60].replace("/", "_").replace(":", "_")
        ext_id = f"social_{platform}_{safe_url}"

        signals_to_create.append({
            "place_id": place_id,
            "platform": platform,
            "confidence": confidence,
            "url": url,
            "ext_id": ext_id,
        })

    print(f"\nSocial signals to create: {len(signals_to_create)}")
    print(f"Skipping website updates — social URLs are NOT canonical websites")

    if signals_to_create:
        platform_counts: dict[str, int] = {}
        for s in signals_to_create:
            platform_counts[s["platform"]] = platform_counts.get(s["platform"], 0) + 1
        for platform, count in sorted(platform_counts.items()):
            print(f"  {platform}: {count}")

    if dry_run:
        print("\nDRY RUN — no writes")
        if signals_to_create[:5]:
            print("Sample signals:")
            for s in signals_to_create[:5]:
                print(f"  {s['place_id'][:8]}... {s['platform']}({s['confidence']}) {s['url'][:60]}")
        return

    inserted = 0
    skipped = 0

    for sig in signals_to_create:
        # Idempotent check
        existing = db.execute(
            select(PlaceSignal.id)
            .where(
                PlaceSignal.place_id == sig["place_id"],
                PlaceSignal.provider == sig["platform"],
                PlaceSignal.signal_type == "creator",
                PlaceSignal.external_event_id == sig["ext_id"],
            )
        ).first()

        if existing:
            skipped += 1
            continue

        signal = PlaceSignal(
            place_id=sig["place_id"],
            provider=sig["platform"],
            signal_type="creator",
            value=sig["confidence"],
            raw_value=sig["url"][:255],
            external_event_id=sig["ext_id"],
        )
        db.add(signal)
        inserted += 1

    # NOTE: We do NOT write social URLs to Place.website.
    # Social profiles are signals, not canonical websites.
    # Place.website is reserved for official business sites and ordering URLs.

    db.commit()
    db.close()
    print(f"\nInserted {inserted} creator signals ({skipped} already existed)")
    print(f"Place.website NOT modified — social URLs stored in PlaceSignal only")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    run(dry_run=args.dry_run)
