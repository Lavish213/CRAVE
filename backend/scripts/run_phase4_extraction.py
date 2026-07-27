"""
Phase A Extraction — CRAVE

Controlled single-place extraction test.
Runs the full pipeline and produces DB proof.

Usage:
    cd backend
    python scripts/run_phase4_extraction.py                  # auto-picks Toast place
    python scripts/run_phase4_extraction.py --place-id <id>  # specific place
    python scripts/run_phase4_extraction.py --dry-run        # no DB writes

Pipeline:
    place.website
        → detect_provider
        → route_provider (Toast/ChowNow/Popmenu)
        → process_extracted_menu
        → emit_menu_claims
        → materialize_menu_truth
        → MenuPublisher.publish()  ← writes to menu_items
        → MenuImageBridge          ← item images → Phase 3
"""
from __future__ import annotations

import argparse
import logging
import sys

sys.path.insert(0, ".")

from sqlalchemy import text

from app.db.session import SessionLocal
from app.db.models.place import Place

from app.services.menu.processing.menu_orchestrator import MenuOrchestrator
from app.services.menu.menu_publisher import MenuPublisher


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def ok(msg: str):
    print(f"  ✅  {msg}")


def fail(msg: str):
    print(f"  ❌  {msg}")


def info(msg: str):
    print(f"  ℹ️   {msg}")


# -----------------------------------------------------------------
# PLACE SELECTION
# -----------------------------------------------------------------

def _pick_toast_place(db) -> Place | None:
    """Pick a Toast place with a known-good URL format."""
    candidates = db.execute(text("""
        SELECT id, name, website FROM places
        WHERE is_active = true
        AND (
            website LIKE '%toasttab.com/local/%'
            OR website LIKE '%order.toasttab.com/online/%'
            OR website LIKE '%toasttab.com/%'
        )
        AND has_menu = false
        ORDER BY RANDOM()
        LIMIT 20
    """)).fetchall()

    if not candidates:
        return None

    for row in candidates:
        place_id, name, website = row
        place = db.query(Place).filter(Place.id == place_id).first()
        if place and place.website:
            logger.info("selected_place id=%s name=%s website=%s", place_id, name, website)
            return place

    return None


def _pick_chownow_place(db) -> Place | None:
    row = db.execute(text("""
        SELECT id FROM places
        WHERE is_active = true
        AND website LIKE '%chownow%'
        AND has_menu = false
        LIMIT 1
    """)).fetchone()
    if row:
        return db.query(Place).filter(Place.id == row[0]).first()
    return None


# -----------------------------------------------------------------
# MAIN
# -----------------------------------------------------------------

def run(place_id: str | None = None, dry_run: bool = False) -> bool:
    """
    Returns True if extraction produced real menu items.
    """
    db = SessionLocal()

    try:
        # ── STEP 1: Select place ─────────────────────────────────────
        section("STEP 1 — Select Place")

        if place_id:
            place = db.query(Place).filter(Place.id == place_id).first()
            if not place:
                fail(f"Place not found: {place_id}")
                return False
        else:
            place = _pick_toast_place(db) or _pick_chownow_place(db)

        if not place:
            fail("No suitable place found — need places with Toast/ChowNow/Popmenu websites")
            return False

        info(f"Place: {place.id}")
        info(f"Name:  {place.name}")
        info(f"URL:   {place.website}")

        if not place.website:
            fail("Place has no website URL")
            return False

        if dry_run:
            info("DRY RUN — skipping DB writes")
            return True

        # ── STEP 2: Run MenuOrchestrator ─────────────────────────────
        section("STEP 2 — Run MenuOrchestrator")

        orchestrator = MenuOrchestrator()

        try:
            result = orchestrator.run_for_place(db=db, place=place)
        except Exception as exc:
            fail(f"Orchestrator failed: {exc}")
            import traceback
            traceback.print_exc()
            return False

        info(f"Extracted items:   {result.extracted_item_count}")
        info(f"Claims emitted:    {result.emitted_claim_count}")
        info(f"Materialized:      {result.materialized}")
        info(f"Sources used:      {result.source_count}")

        if result.extracted_item_count == 0:
            fail("ZERO items extracted — check URL / provider detection")
            _print_debug_hint(place)
            return False

        ok(f"{result.extracted_item_count} items extracted from live source")

        if result.emitted_claim_count == 0:
            fail("ZERO claims emitted — pipeline blocked somewhere")
            return False

        if not result.materialized:
            fail("materialize_menu_truth returned None — check claims table")
            return False

        ok("Claims emitted and truth materialized")

        # ── STEP 3: Publish to menu_items ────────────────────────────
        section("STEP 3 — Publish to menu_items (cache)")

        try:
            publisher = MenuPublisher()
            written = publisher.publish(place_id=place.id)
        except Exception as exc:
            fail(f"MenuPublisher failed: {exc}")
            import traceback
            traceback.print_exc()
            return False

        if written == 0:
            fail("MenuPublisher wrote 0 items — check place_truths table")
            return False

        ok(f"MenuPublisher wrote {written} rows to menu_items")

        # ── STEP 4: DB Proof ─────────────────────────────────────────
        section("STEP 4 — DB Proof")

        rows = db.execute(text("""
            SELECT name, category, price
            FROM menu_items
            WHERE place_id = :pid
            ORDER BY category, name
            LIMIT 10
        """), {"pid": place.id}).fetchall()

        if not rows:
            fail("menu_items table shows 0 rows for this place")
            return False

        ok(f"Sample menu_items for '{place.name}':")
        for r in rows:
            name, category, price = r
            price_str = f"${price:.2f}" if price else "no price"
            print(f"    [{category or 'Other':20s}]  {name:<40s}  {price_str}")

        # Check images
        image_rows = db.execute(text("""
            SELECT COUNT(*), AVG(quality_score),
                   SUM(CASE WHEN visibility_status = 'candidate_primary' THEN 1 ELSE 0 END)
            FROM place_images
            WHERE place_id = :pid
        """), {"pid": place.id}).fetchone()

        img_count, avg_quality, primary_count = image_rows
        info(f"Place images: {img_count or 0}  avg_quality={avg_quality:.3f if avg_quality else 'N/A'}  candidate_primary={primary_count or 0}")

        # Check if bridge ran (images have quality_score)
        bridge_rows = db.execute(text("""
            SELECT COUNT(*)
            FROM place_images
            WHERE place_id = :pid
            AND quality_score IS NOT NULL
            AND content_type IS NOT NULL
        """), {"pid": place.id}).fetchone()

        bridge_count = bridge_rows[0] if bridge_rows else 0
        if bridge_count > 0:
            ok(f"Phase 3 bridge: {bridge_count} images classified")
        else:
            info("No item images from this extraction (provider may not include item imageUrls)")

        # ── VERDICT ──────────────────────────────────────────────────
        section("PHASE A VERDICT")
        ok(f"PASS — {written} real menu items in DB for place '{place.name}'")
        ok("Pipeline: extraction → claims → truth → menu_items → Phase 3")
        print()

        return True

    finally:
        db.close()


def _print_debug_hint(place):
    from app.services.menu.extraction.provider.provider_detector import detect_provider
    try:
        provider = detect_provider("", place.website)
        info(f"Provider detected: {provider or 'NONE'}")
        if not provider:
            info("URL does not match any known provider pattern")
            info("Orchestrator will fall back to HTML extraction")
    except Exception:
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--place-id", help="Place UUID to extract")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    success = run(place_id=args.place_id, dry_run=args.dry_run)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
