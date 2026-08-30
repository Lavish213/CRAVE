"""
Phase 4 Audit Script — CRAVE

Verifies:
1. Menu items in DB (count, null field check)
2. Item images in place_images (from provider sources)
3. Phase 3 compliance (quality_score, content_type, visibility_status non-null)
4. Place traces (5 places with full lineage)
5. 20-place sample (extractor success rate, image coverage)
6. Anti-fake check (no placeholder/mock URLs)

Run:
    cd backend
    python scripts/run_phase4_audit.py
"""
from __future__ import annotations

import logging
import sys
from textwrap import dedent

from sqlalchemy import text

sys.path.insert(0, ".")

from app.db.session import SessionLocal  # noqa: E402
from app.services.menu.menu_publisher import is_obvious_placeholder_item  # noqa: E402


logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# Use domain/path-level patterns that won't false-positive on opaque photo tokens.
# These are substrings that only appear in clearly fake/test URLs, not in
# legitimate Google Places photo hashes.
PLACEHOLDER_PATTERNS = [
    "via.placeholder.com",
    "placeholder.com",
    "example.com/",
    "localhost:",
    "test-image.png",
    "fake-image",
    "mock-image",
    "dummy-image",
]


def _run_query(db, sql: str, params: dict | None = None):
    result = db.execute(text(sql), params or {})
    return result


def section(title: str):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def ok(msg: str):
    print(f"  ✅  {msg}")


def warn(msg: str):
    print(f"  ⚠️   {msg}")


def fail(msg: str):
    print(f"  ❌  {msg}")


def main():
    db = SessionLocal()
    issues: list[str] = []

    try:
        # ============================================================
        # 1. MENU DATA IN DB
        # ============================================================
        section("1 — MENU DATA IN DB")

        # place_truths is the primary source (JSON blob written by materialize_menu_truth)
        row = _run_query(db, "SELECT COUNT(*) FROM place_truths WHERE truth_type = 'menu'").fetchone()
        total_truths = row[0] if row else 0
        print(f"  place_truths (menu):  {total_truths:,}  ← primary source")

        # menu_items is the published cache (written by MenuPublisher.publish())
        row = _run_query(db, "SELECT COUNT(*) FROM menu_items").fetchone()
        total_items = row[0] if row else 0
        print(f"  menu_items (cache):   {total_items:,}  ← published layer")

        if total_truths == 0 and total_items == 0:
            fail("No menu data in DB — extraction has not run")
            issues.append("BLOCKER: menu_items = 0 AND place_truths(menu) = 0")
        elif total_truths > 0 and total_items == 0:
            warn("place_truths has data but menu_items is empty — MenuPublisher.publish() not called")
            issues.append("HIGH: place_truths has menus but menu_items cache is empty")
        else:
            ok(f"{total_items:,} menu items in cache DB")

        # NULL field audit
        null_checks = [
            ("name", "SELECT COUNT(*) FROM menu_items WHERE name IS NULL OR name = ''"),
            ("category", "SELECT COUNT(*) FROM menu_items WHERE category IS NULL OR category = ''"),
        ]

        for field, sql in null_checks:
            row = _run_query(db, sql).fetchone()
            count = row[0] if row else 0
            if count > 0:
                warn(f"menu_items.{field} NULL count: {count:,}")
            else:
                ok(f"menu_items.{field} — no NULLs (or expected NULLs)")

        # Items with price. ``price_cents`` is the canonical integer-cents
        # column; the old ``price`` column never existed in the deployed
        # schema. Keep this audit aligned with MenuItem so a readiness check
        # cannot fail before reaching the image integrity gates.
        row = _run_query(
            db,
            "SELECT COUNT(*) FROM menu_items WHERE price_cents IS NOT NULL",
        ).fetchone()
        priced = row[0] if row else 0
        pct = (priced / total_items * 100) if total_items else 0
        print(f"  Items with price: {priced:,} ({pct:.1f}%)")

        if total_items > 0 and pct < 20:
            warn(f"Only {pct:.1f}% of items have prices — low coverage")
            issues.append(f"MEDIUM: only {pct:.1f}% items have price")

        # ============================================================
        # 2. PLACE IMAGE PHASE 3 COMPLIANCE
        # ============================================================
        section("2 — PLACE IMAGES (Phase 3 compliance)")

        row = _run_query(db, "SELECT COUNT(*) FROM place_images").fetchone()
        total_images = row[0] if row else 0
        print(f"  Total place_images: {total_images:,}")

        phase3_checks = [
            ("quality_score NULL", "SELECT COUNT(*) FROM place_images WHERE quality_score IS NULL"),
            ("content_type NULL", "SELECT COUNT(*) FROM place_images WHERE content_type IS NULL"),
            ("visibility_status NULL/empty", "SELECT COUNT(*) FROM place_images WHERE visibility_status IS NULL OR visibility_status = ''"),
        ]

        for label, sql in phase3_checks:
            row = _run_query(db, sql).fetchone()
            count = row[0] if row else 0
            pct = (count / total_images * 100) if total_images else 0
            if count > 0:
                warn(f"{label}: {count:,} ({pct:.1f}%)")
                if pct > 5:
                    issues.append(f"HIGH: {count} place_images with {label}")
            else:
                ok(f"{label}: 0")

        # Hidden primaries (hard invariant violation)
        row = _run_query(
            db,
            "SELECT COUNT(*) FROM place_images WHERE is_primary = true AND visibility_status = 'hidden'",
        ).fetchone()
        hidden_primary = row[0] if row else 0
        if hidden_primary > 0:
            fail(f"Hidden primary images: {hidden_primary:,} — INVARIANT VIOLATION")
            issues.append(f"BLOCKER: {hidden_primary} hidden primary images")
        else:
            ok("No hidden primary images")

        # Places with multiple primaries
        row = _run_query(
            db,
            dedent("""
                SELECT COUNT(*) FROM (
                    SELECT place_id FROM place_images
                    WHERE is_primary = true
                    GROUP BY place_id
                    HAVING COUNT(*) > 1
                ) t
            """),
        ).fetchone()
        dup_primary = row[0] if row else 0
        if dup_primary > 0:
            fail(f"Places with duplicate primaries: {dup_primary:,} — INVARIANT VIOLATION")
            issues.append(f"BLOCKER: {dup_primary} places with duplicate primaries")
        else:
            ok("No duplicate primaries")

        # ============================================================
        # 3. ANTI-FAKE CHECK
        # ============================================================
        section("3 — ANTI-FAKE CHECK")

        for pattern in PLACEHOLDER_PATTERNS:
            sql = f"SELECT COUNT(*) FROM place_images WHERE url LIKE :pattern"
            row = _run_query(db, sql, {"pattern": f"%{pattern}%"}).fetchone()
            count = row[0] if row else 0
            if count > 0:
                fail(f"Placeholder pattern '{pattern}' found in {count} image URLs")
                issues.append(f"BLOCKER: {count} fake images with pattern '{pattern}'")

        # Check menu items for fake names — use whole-word patterns to avoid
        # false-positives like "intestine" (matches "test") or "mocktail" (matches "mock")
        item_rows = _run_query(
            db,
            "SELECT name, price_cents, description FROM menu_items",
        ).fetchall()
        fake_items = sum(
            is_obvious_placeholder_item(
                name=row[0] or "",
                price_cents=row[1],
                description=row[2],
            )
            for row in item_rows
        )
        if fake_items > 0:
            fail(f"Exact fake menu item names found: {fake_items}")
            issues.append(f"HIGH: {fake_items} menu items with exact fake names")
        else:
            ok("No fake/mock/test menu item names detected")

        # ============================================================
        # 4. PLACE TRACES (5 places with menu items)
        # ============================================================
        section("4 — PLACE TRACES (5 places)")

        traced = _run_query(
            db,
            dedent("""
                SELECT
                    p.id,
                    p.name,
                    COUNT(DISTINCT mi.id) AS item_count,
                    COUNT(DISTINCT pi.id) AS image_count,
                    SUM(CASE WHEN pi.is_primary THEN 1 ELSE 0 END) AS has_primary,
                    AVG(pi.quality_score) AS avg_quality
                FROM places p
                JOIN menu_items mi ON mi.place_id = p.id AND mi.is_active = true
                LEFT JOIN place_images pi ON pi.place_id = p.id
                WHERE p.is_active = true
                GROUP BY p.id, p.name
                HAVING COUNT(DISTINCT mi.id) >= 2
                ORDER BY item_count DESC
                LIMIT 5
            """),
        ).fetchall()

        if not traced:
            fail("No places found with menu items — extraction has not run or produced no DB writes")
            issues.append("BLOCKER: 0 places have menu items in DB")
        else:
            for row in traced:
                place_id, name, item_count, image_count, has_primary, avg_quality = row
                q = f"{avg_quality:.3f}" if avg_quality else "none"
                print(f"  [{place_id[:8]}] {name[:40]:<40}  items={item_count}  images={image_count}  primary={bool(has_primary)}  avg_quality={q}")

        # ============================================================
        # 5. 20-PLACE SAMPLE — extractor coverage
        # ============================================================
        section("5 — 20-PLACE SAMPLE")

        row = _run_query(db, "SELECT COUNT(DISTINCT place_id) FROM menu_items").fetchone()
        places_with_menu = row[0] if row else 0

        row = _run_query(db, "SELECT COUNT(*) FROM places WHERE is_active = true").fetchone()
        active_places = row[0] if row else 0

        coverage = (places_with_menu / active_places * 100) if active_places else 0
        print(f"  Places with menus: {places_with_menu:,} / {active_places:,} ({coverage:.1f}%)")

        row = _run_query(
            db,
            dedent("""
                SELECT COUNT(DISTINCT pi.place_id)
                FROM place_images pi
                WHERE pi.content_type IS NOT NULL
            """),
        ).fetchone()
        places_with_images = row[0] if row else 0
        img_coverage = (places_with_images / active_places * 100) if active_places else 0
        print(f"  Places with scored images: {places_with_images:,} ({img_coverage:.1f}%)")

        # visibility distribution
        rows = _run_query(
            db,
            dedent("""
                SELECT visibility_status, COUNT(*) AS cnt
                FROM place_images
                GROUP BY visibility_status
                ORDER BY cnt DESC
            """),
        ).fetchall()
        print("  Visibility distribution:")
        for r in rows:
            vs, cnt = r
            pct = cnt / total_images * 100 if total_images else 0
            print(f"    {vs or 'NULL':<25} {cnt:>8,}  ({pct:.1f}%)")

        # ============================================================
        # FINAL VERDICT
        # ============================================================
        section("PHASE 4 VERDICT")

        blockers = [i for i in issues if i.startswith("BLOCKER")]
        high = [i for i in issues if i.startswith("HIGH")]
        medium = [i for i in issues if i.startswith("MEDIUM")]

        if blockers:
            status = "FAIL"
        elif high:
            status = "FAIL (HIGH issues)"
        elif medium:
            status = "PASS WITH WARNINGS"
        else:
            status = "PASS"

        print(f"\n  STATUS: {status}")

        if blockers:
            print("\n  BLOCKERS:")
            for b in blockers:
                print(f"    {b}")

        if high:
            print("\n  HIGH:")
            for h in high:
                print(f"    {h}")

        if medium:
            print("\n  MEDIUM:")
            for m in medium:
                print(f"    {m}")

        if not issues:
            ok("No issues found")

        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
