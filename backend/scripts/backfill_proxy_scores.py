"""
backfill_proxy_scores.py

Computes a data-completeness proxy score for places that have no real signal
score.  Never decreases an existing score.

Formula v2
----------
+0.10  has at least 1 image
+0.03  has 3+ images            (total 0.13 for well-imaged)
+0.10  has website
+0.05  has address
+0.07  has specific category    (not Restaurant / Bar / Other / '' / None)

Max: 0.35  → qualifies as GEM
Path to SOLID without images: website(0.10) + address(0.05) + specific_cat(0.07) = 0.22 ✓
Path to GEM: 3img(0.13) + website(0.10) + address(0.05) + specific_cat(0.07) = 0.35

Usage
-----
    python scripts/backfill_proxy_scores.py [--dry-run] [--threshold 0.35]
"""
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

# ── allow imports from project root ────────────────────────────────────────
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import create_engine, text
from app.config.settings import settings

# Categories that provide no useful signal
GENERIC_CATEGORIES = {
    "restaurant", "restaurants",
    "bar", "bars",
    "other", "others",
    "",
}

BATCH_SIZE = 500


def tier(score: float) -> str:
    if score >= 0.42:
        return "CRAVE_PICK"
    if score >= 0.32:
        return "GEM"
    if score >= 0.22:
        return "SOLID"
    return "NEW"


def compute_proxy(image_count: int, has_website: bool, has_address: bool, specific_cat: bool) -> float:
    score = 0.0
    if image_count >= 1:
        score += 0.10
    if image_count >= 3:
        score += 0.03
    if has_website:
        score += 0.10
    if has_address:
        score += 0.05
    if specific_cat:
        score += 0.07
    return round(score, 4)


def main(dry_run: bool, threshold: float) -> None:
    engine = create_engine(settings.resolved_database_url)

    with engine.connect() as conn:
        # ── fetch candidates ────────────────────────────────────────────────
        rows = conn.execute(text("""
            SELECT
                p.id,
                p.rank_score,
                p.website,
                p.address,
                p.grubhub_url,
                (
                    SELECT COUNT(*)
                    FROM place_images pi
                    WHERE pi.place_id = p.id
                ) AS image_count,
                (
                    SELECT c.name
                    FROM place_categories pc
                    JOIN categories c ON c.id = pc.category_id
                    WHERE pc.place_id = p.id
                    LIMIT 1
                ) AS primary_category
            FROM places p
            WHERE p.is_active = 1
              AND p.rank_score < :threshold
        """), {"threshold": threshold}).fetchall()

        print(f"Candidates (rank_score < {threshold}): {len(rows):,}")

        before_dist: Counter = Counter()
        after_dist: Counter = Counter()
        updates: list[dict] = []

        for row in rows:
            place_id = row[0]
            current_score = float(row[1] or 0.0)
            has_website = bool(row[2] and str(row[2]).strip())
            has_address = bool(row[3] and str(row[3]).strip())
            image_count = int(row[5] or 0)
            primary_cat = (row[6] or "").strip().lower()
            specific_cat = primary_cat not in GENERIC_CATEGORIES

            proxy = compute_proxy(image_count, has_website, has_address, specific_cat)
            new_score = max(current_score, proxy)

            before_dist[tier(current_score)] += 1
            after_dist[tier(new_score)] += 1

            if new_score != current_score:
                updates.append({"id": place_id, "score": new_score})

        print(f"\nPlaces that will change: {len(updates):,}")

        print("\nBefore tier distribution (candidates only):")
        for t in ["CRAVE_PICK", "GEM", "SOLID", "NEW"]:
            print(f"  {t:12s}  {before_dist[t]:6,}")

        print("\nAfter tier distribution (candidates only):")
        for t in ["CRAVE_PICK", "GEM", "SOLID", "NEW"]:
            print(f"  {t:12s}  {after_dist[t]:6,}")

        if dry_run:
            print("\n[DRY RUN] No changes written.")
            return

        # ── apply in batches ────────────────────────────────────────────────
        total_written = 0
        for i in range(0, len(updates), BATCH_SIZE):
            batch = updates[i : i + BATCH_SIZE]
            conn.execute(
                text("UPDATE places SET rank_score = :score WHERE id = :id"),
                batch,
            )
            conn.commit()
            total_written += len(batch)
            print(f"  wrote {total_written:,} / {len(updates):,}", end="\r")

        print(f"\nDone. Updated {total_written:,} places.")

        # ── full DB tier summary ────────────────────────────────────────────
        full = conn.execute(text("""
            SELECT rank_score FROM places WHERE is_active = 1
        """)).fetchall()

        full_dist: Counter = Counter()
        for (s,) in full:
            full_dist[tier(float(s or 0.0))] += 1

        total_active = sum(full_dist.values())
        print(f"\nFull DB tier distribution ({total_active:,} active places):")
        for t in ["CRAVE_PICK", "GEM", "SOLID", "NEW"]:
            pct = 100 * full_dist[t] / total_active if total_active else 0
            print(f"  {t:12s}  {full_dist[t]:6,}  ({pct:.1f}%)")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill proxy rank scores")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.20,
        help="Only touch places with rank_score below this value (default: 0.20)",
    )
    args = parser.parse_args()
    main(dry_run=args.dry_run, threshold=args.threshold)
