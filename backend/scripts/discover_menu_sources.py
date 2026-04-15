"""
discover_menu_sources.py

Probes Place.website to find menu provider URLs (Toast, Clover, PopMenu, etc.).

For each place that has:
  - website IS NOT NULL and not empty
  - has_menu = FALSE
  - menu_source_url IS NULL  (not already discovered)

Steps:
  1. Probe the website to detect the menu provider URL.
  2. If confidence >= 0.7: save menu_source_url to Place.
  3. With --extract: run full menu extraction immediately after discovery.

Idempotent — skips places that already have menu_source_url set.
Domain cache prevents re-fetching the same domain in the same run.

Usage:
    python scripts/discover_menu_sources.py --dry-run
    python scripts/discover_menu_sources.py --limit 50
    python scripts/discover_menu_sources.py --limit 100 --extract
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select, update

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.services.menu.discovery.website_provider_probe import probe_website, ProbeResult


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)


def _domain(website: str) -> str:
    try:
        return urlparse(website).netloc.lower()
    except Exception:
        return website[:60]


def run(*, dry_run: bool = False, limit: int = 100, extract: bool = False) -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Place.id, Place.name, Place.website, Place.rank_score)
            .where(
                Place.is_active.is_(True),
                Place.website.isnot(None),
                Place.website != "",
                Place.has_menu.is_(False),
                Place.menu_source_url.is_(None),
            )
            .order_by(Place.rank_score.desc())
            .limit(limit)
        ).fetchall()

        print(f"Candidates: {len(rows)} places (website set, no menu, no menu_source_url)")
        if dry_run:
            print("DRY RUN — probe runs, no DB writes\n")
        else:
            print()

        found = 0
        skipped = 0

        # Domain cache: avoid probing the same domain more than once per run
        domain_cache: dict[str, ProbeResult] = {}

        for row in rows:
            website = (row.website or "").strip()
            if not website:
                skipped += 1
                continue

            dom = _domain(website)

            if dom in domain_cache:
                result = domain_cache[dom]
            else:
                result = probe_website(website)
                domain_cache[dom] = result
                time.sleep(0.3)  # polite inter-domain delay

            if not result.found:
                skipped += 1
                print(f"  SKIP  {row.name!r:40s}  conf={result.confidence:.2f}")
                continue

            found += 1
            print(f"  FOUND {row.name!r:40s}  {result.provider}  {result.menu_source_url}")

            if dry_run:
                continue

            # Save menu_source_url
            db.execute(
                update(Place)
                .where(Place.id == row.id)
                .values(menu_source_url=result.menu_source_url[:1024])
            )
            db.commit()

            if extract:
                try:
                    from app.services.menu.extraction.extract_menu_from_url import (
                        extract_menu_from_url,
                    )
                    extracted = extract_menu_from_url(
                        db=db,
                        place_id=row.id,
                        url=result.menu_source_url,
                    )
                    item_count = len(extracted.items) if extracted else 0
                    print(f"    → extracted {item_count} items")
                except Exception as exc:
                    print(f"    → extraction failed: {exc}")

        print(f"\nDone: {found} discovered, {skipped} skipped")
        if dry_run:
            print("DRY RUN — no writes made")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Discover menu source URLs from Place.website"
    )
    parser.add_argument("--dry-run", action="store_true", help="Probe but do not write to DB")
    parser.add_argument("--limit", type=int, default=100, help="Max places to process")
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Run menu extraction immediately after discovery",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit, extract=args.extract)
