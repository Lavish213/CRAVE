"""
One-off cleanup: deactivate Places that were promoted from Google Places
results despite not actually being restaurants — grocery stores, dollar
stores, gas stations, pharmacies, etc. that Google's broad "food"/"store"
Nearby Search types let through before this session's fix to
app/services/ingest/google_places_ingest.py (SEARCH_TYPES no longer
includes "food"; _NON_RESTAURANT_TYPES now hard-excludes these categories
at ingestion time going forward).

This script only cleans up what's ALREADY in the database — the code fix
prevents new junk, this removes existing junk. Soft-delete only (sets
is_active=False); nothing is ever hard-deleted, so this is fully
reversible by flipping is_active back to True for any row it touches.

Usage:
    # Dry run (default) — prints what WOULD be deactivated, changes nothing.
    python scripts/deactivate_non_restaurant_places.py

    # Actually deactivate.
    python scripts/deactivate_non_restaurant_places.py --apply

Run this against the real database — set DATABASE_URL to Railway's
production Postgres connection string first (Railway dashboard -> Postgres
service -> Variables -> DATABASE_URL), e.g.:

    DATABASE_URL="postgresql://..." python scripts/deactivate_non_restaurant_places.py --apply
"""
from __future__ import annotations

import argparse
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.db.models.discovery_candidate import DiscoveryCandidate
from app.services.ingest.google_places_ingest import _NON_RESTAURANT_TYPES, _TYPE_TO_HINT

# Genuine food-service types (restaurant, cafe, bakery, bar, and the various
# cuisine-specific Google types). A place carrying one of these alongside a
# broader _NON_RESTAURANT_TYPES hit is a false positive, not junk — e.g. a
# pizzeria that also holds a liquor license (`liquor_store`), or a bakery
# Google additionally tags `wholesaler`. Found running this script for real:
# it flagged "Curry Pizza House" locations, "The Plant Café Organic", and a
# dozen other bakeries/cafes this way before this exemption existed.
_FOOD_SERVICE_TYPES = frozenset(_TYPE_TO_HINT)


# Belt-and-suspenders name check for well-known non-restaurant chains, in
# case a row's original DiscoveryCandidate/raw_payload is missing or its
# Google `types` didn't include one of _NON_RESTAURANT_TYPES for some
# reason (Google's typing isn't perfectly consistent city to city).
_KNOWN_NON_RESTAURANT_NAME_SUBSTRINGS = [
    "dollar general", "dollar tree", "family dollar",
    "trader joe", "whole foods", "safeway", "walmart", "target",
    "costco", "kroger", "publix", "albertsons", "vons", "ralphs",
    "cvs", "walgreens", "rite aid", "7-eleven", "7 eleven",
    "super king", "smart & final", "food 4 less", "grocery outlet",
    "home depot", "lowe's", "lowes ",
]

# Same false-positive shape as _FOOD_SERVICE_TYPES above, but for the name
# check: an in-store food concession — a Starbucks kiosk inside a Target, an
# AFC Sushi counter inside a Safeway, a Costco Food Court — is a distinct,
# real food-service business, not the host store itself, even though the
# host store's name is right there in it. Found running this script for
# real: "Costco Food Court", "AFC Sushi @ Safeway #1953", "Starbucks (in
# Target)", "Target Cafe" all got swept up by the chain-name check above.
# Deliberately NOT included: "canteen" ("Canteen @ Costco #1341 Breakroom"
# reads as an employee-only cafeteria, not a public place to eat) and plain
# "food" (would exempt "Advantage Food Sampling Program @ Safeway #1502",
# a promotional sampling table, not a restaurant).
_IN_STORE_FOOD_CONCESSION_SUBSTRINGS = [
    "food court", "starbucks", "cafe", "afc ",
]


def _find_candidates_to_deactivate(db):
    places = db.query(Place).filter(Place.is_active.is_(True)).all()

    # Batch-fetch every resolved DiscoveryCandidate for these places in one
    # query instead of one query per place — the original per-place query
    # (an N+1) was fine in tests against a handful of fixture rows but took
    # this script from instant to minutes-long against the real production
    # catalog (thousands of active places, each a separate round trip).
    place_ids = [p.id for p in places]
    candidates_by_place_id: dict[str, list[DiscoveryCandidate]] = defaultdict(list)
    if place_ids:
        all_candidates = (
            db.query(DiscoveryCandidate)
            .filter(DiscoveryCandidate.resolved_place_id.in_(place_ids))
            .all()
        )
        for candidate in all_candidates:
            candidates_by_place_id[candidate.resolved_place_id].append(candidate)

    flagged = []

    for place in places:
        reason = None

        name_lower = (place.name or "").lower()
        is_in_store_concession = any(
            substr in name_lower for substr in _IN_STORE_FOOD_CONCESSION_SUBSTRINGS
        )
        if not is_in_store_concession:
            for substr in _KNOWN_NON_RESTAURANT_NAME_SUBSTRINGS:
                if substr in name_lower:
                    reason = f"name matches known non-restaurant chain ({substr!r})"
                    break

        if not reason:
            # A place can have more than one resolved DiscoveryCandidate —
            # the same real place discovered via multiple sources/searches
            # and deduplicated down to one Place, each candidate keeping
            # its own resolved_place_id pointing at it. .one_or_none()
            # assumed exactly one and crashed the instant a place had more
            # than that. Checking all of them and taking the first
            # non-restaurant hit is both crash-proof and more correct: if
            # ANY discovery source flagged this place's types as
            # non-restaurant, that's real signal even when another
            # candidate for the same place didn't carry that data.
            for candidate in candidates_by_place_id.get(place.id, []):
                if not isinstance(candidate.raw_payload, dict):
                    continue
                types = candidate.raw_payload.get("types") or []
                if _FOOD_SERVICE_TYPES.intersection(types):
                    # A genuine food-service type on this same candidate
                    # outweighs a broader non-restaurant type also present —
                    # this is a real restaurant/cafe/bakery/bar, not junk.
                    continue
                hit = _NON_RESTAURANT_TYPES.intersection(types)
                if hit:
                    reason = f"Google types include {sorted(hit)}"
                    break

        if reason:
            flagged.append((place, reason))

    return flagged


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Actually deactivate (default is dry-run).")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        flagged = _find_candidates_to_deactivate(db)

        if not flagged:
            print("Nothing found to deactivate.")
            return

        print(f"{'Deactivating' if args.apply else 'Would deactivate'} {len(flagged)} place(s):\n")
        for place, reason in flagged:
            print(f"  - {place.name}  (id={place.id})  -- {reason}")

        if args.apply:
            for place, _ in flagged:
                place.is_active = False
            db.commit()
            print(f"\nDone. {len(flagged)} place(s) deactivated (is_active=False).")
        else:
            print("\nDry run only — nothing changed. Re-run with --apply to actually deactivate.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
