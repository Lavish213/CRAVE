"""
Read-only report on menu coverage across the active catalog — answers
"how much of the catalog actually has a menu, and why not for the rest"
without needing to eyeball individual place pages.

Usage:
    DATABASE_URL="<railway postgres url>" python scripts/menu_coverage_report.py
    DATABASE_URL="<railway postgres url>" python scripts/menu_coverage_report.py --city-slug oakland

Changes nothing — pure reporting.
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import or_

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.city import City
from app.db.models.menu_item import MenuItem
from app.db.models.menu_source import MenuSource
from app.services.workers.menu_worker import _not_in_backoff_clause


def _pct(n: int, total: int) -> str:
    if total == 0:
        return "n/a"
    return f"{100 * n / total:.1f}%"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--city-slug", default=None, help="Limit to one city (by slug).")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        query = db.query(Place).filter(Place.is_active.is_(True))

        if args.city_slug:
            city = db.query(City).filter(City.slug == args.city_slug).one_or_none()
            if not city:
                print(f"No city found with slug={args.city_slug!r}")
                return
            query = query.filter(Place.city_id == city.id)
            print(f"Scope: {city.name} ({city.slug})\n")
        else:
            print("Scope: all active cities\n")

        places = query.all()
        total = len(places)

        if total == 0:
            print("No active places found.")
            return

        has_menu = [p for p in places if p.has_menu]
        no_menu = [p for p in places if not p.has_menu]

        has_source = [
            p for p in no_menu
            if (p.website or p.grubhub_url or p.menu_source_url)
        ]
        no_source_at_all = [p for p in no_menu if p not in has_source]

        now = datetime.now(timezone.utc)
        in_backoff = []
        eligible_now = []
        never_attempted = []

        never_attempted = [
            p for p in has_source if p.menu_extraction_attempted_at is None
        ]
        # One set-based query, not one round trip per place. The old report
        # issued ~13k production queries and could time out before printing
        # anything useful.
        source_ids = [p.id for p in has_source]
        eligible_ids = {
            row[0]
            for row in (
                db.query(Place.id)
                .filter(Place.id.in_(source_ids), _not_in_backoff_clause(now))
                .all()
            )
        } if source_ids else set()
        eligible_now = [p for p in has_source if p.id in eligible_ids]
        in_backoff = [p for p in has_source if p.id not in eligible_ids]

        stuck = [p for p in has_source if (p.menu_extraction_failure_count or 0) >= 4]

        print(f"Active places:                        {total}")
        print(f"  Has a menu (>= materialized truth):  {len(has_menu)}  ({_pct(len(has_menu), total)})")
        print(f"  No menu yet:                         {len(no_menu)}  ({_pct(len(no_menu), total)})")
        print()
        print("Of the places with no menu yet:")
        print(f"  No website/Grubhub/menu source at all — CANNOT be attempted: "
              f"{len(no_source_at_all)}  ({_pct(len(no_source_at_all), len(no_menu))})")
        print(f"  Has a source, never attempted yet:   {len(never_attempted)}")
        print(f"  Has a source, eligible right now:    {len(eligible_now)}")
        print(f"  Has a source, currently in backoff:  {len(in_backoff)}")
        print(f"  Has a source, failed 4+ times ('stuck'): {len(stuck)}  ({_pct(len(stuck), len(has_source) or 1)})")
        print()

        if stuck:
            print(f"Top 10 stuck places (failed 4+ times) — worth checking by hand,")
            print(f"these are the ones most likely revealing an extractor gap:")
            stuck_sorted = sorted(stuck, key=lambda p: -(p.menu_extraction_failure_count or 0))
            for p in stuck_sorted[:10]:
                source = p.website or p.grubhub_url or p.menu_source_url
                print(f"  - {p.name!r:40s} failures={p.menu_extraction_failure_count:<4} source={source}")
            print()

        if no_source_at_all:
            categories = Counter()
            # No direct category column on Place — just flag the count;
            # cross-reference discovery_candidates by hand if you need
            # per-category breakdown.
            print(f"{len(no_source_at_all)} active places have NO website, Grubhub URL, or menu "
                  f"source URL at all — the menu worker cannot even attempt these. This is a "
                  f"data-enrichment gap (need a website-discovery pass), not an extraction-quality one.")

        source_provider_counts = Counter(
            provider or "<missing>"
            for (provider,) in db.query(MenuSource.provider).filter(
                MenuSource.is_active.is_(True)
            ).all()
        )
        item_provider_counts = Counter(
            provider or "<missing>"
            for (provider,) in db.query(MenuItem.provider).filter(
                MenuItem.is_active.is_(True)
            ).all()
        )
        print("\nActive discovered menu sources by provider:")
        for provider, count in source_provider_counts.most_common():
            print(f"  {provider:20s} {count}")
        print("Active materialized menu items by provider:")
        for provider, count in item_provider_counts.most_common():
            print(f"  {provider:20s} {count}")
        missing_lineage = item_provider_counts.get("<missing>", 0)
        total_items = sum(item_provider_counts.values())
        print(
            f"Provider lineage missing on materialized items: {missing_lineage} "
            f"({_pct(missing_lineage, total_items)})"
        )

    finally:
        db.close()


if __name__ == "__main__":
    main()
