"""
Phase 4 Batch Extraction — CRAVE

Runs MasterDataOrchestrator.ensure_place() for all places that need menus.

Priority order:
    1. Grubhub-linked places with no menu (have structured payload data)
    2. Provider-detected places with no menu (Toast, ChowNow, Clover, etc.)
    3. Any active place with a website and no menu

Smart mode (--priority smart):
    Scores every candidate by expected menu yield, skips known-blocked sources,
    and runs the highest-scoring targets first. Beats random ordering.

Per-place logging: extractor used, items created, fallback used, errors.
Aggregate stats: success rate, failure rate, fallback rate, avg items.

--limit is required (max 200) and, without --run, this only previews the
target count and a sample of place IDs/names -- it does not execute.
This path (ExtractionController) has a materially weaker quality gate
than menu_extraction_router.py's, so keep batches small and spot-check
results between runs.

Run:
    cd backend
    python scripts/run_phase4_batch.py --limit N --priority grubhub|provider|web|all|smart [--run]

Examples:
    python scripts/run_phase4_batch.py --limit 50 --priority smart          # preview
    python scripts/run_phase4_batch.py --limit 50 --priority smart --run    # execute
    python scripts/run_phase4_batch.py --limit 50 --priority grubhub --run
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from dataclasses import dataclass, field
from typing import List, Optional

sys.path.insert(0, ".")

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.db.models.place import Place
from app.services.data.master_data_orchestrator import MasterDataOrchestrator, MasterDataResult
from app.services.data.target_selector import SmartTargetSelector


logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
logger = logging.getLogger("run_phase4_batch")

# This script's places go through ExtractionController + MenuOrchestrator.
# run_with_items() -- a materially less-guarded path than
# menu_extraction_router.py's own ranker/entity checks (see PR #117 and
# menu_pipeline.py's _is_low_quality for the shared quality floor both
# paths do go through). No preview/confirmation existed here before;
# --run + this cap now match run_menu_backlog_canary.py's discipline.
MAX_BATCH_SIZE = 200


# =========================================================
# PRIORITY QUERY HELPERS
# =========================================================

def _fetch_grubhub_places(db: Session, limit: Optional[int]) -> List[str]:
    """Places with grubhub_url but no menu items."""
    sql = """
        SELECT p.id
        FROM places p
        LEFT JOIN (
            SELECT place_id, COUNT(*) AS cnt
            FROM menu_items
            GROUP BY place_id
        ) mi ON mi.place_id = p.id
        WHERE p.is_active = true
          AND p.grubhub_url IS NOT NULL
          AND p.grubhub_url != ''
          AND (mi.cnt IS NULL OR mi.cnt = 0)
        ORDER BY p.master_score DESC
        {limit_clause}
    """
    clause = f"LIMIT {limit}" if limit else ""
    rows = db.execute(text(sql.format(limit_clause=clause))).fetchall()
    return [r[0] for r in rows]


def _fetch_provider_places(db: Session, limit: Optional[int]) -> List[str]:
    """Places with provider-pattern website (toast/chownow/square) but no menu.
    Excludes clover.com (provider homepage, not restaurant-specific).
    Excludes squareup.com without /store/ (marketing page).
    """
    sql = """
        SELECT p.id
        FROM places p
        LEFT JOIN (
            SELECT place_id, COUNT(*) AS cnt
            FROM menu_items
            GROUP BY place_id
        ) mi ON mi.place_id = p.id
        WHERE p.is_active = true
          AND p.website IS NOT NULL
          AND p.website != ''
          AND (mi.cnt IS NULL OR mi.cnt = 0)
          AND (
               p.website LIKE '%toasttab.com%'
            OR p.website LIKE '%chownow.com%'
            OR p.website LIKE '%square.site%'
            OR (p.website LIKE '%squareup.com%' AND p.website LIKE '%/store/%')
            OR p.website LIKE '%popmenu.com%'
          )
          AND p.website NOT LIKE '%www.clover.com%'
          AND p.website NOT LIKE '%dashboard.clover.com%'
        ORDER BY p.master_score DESC
        {limit_clause}
    """
    clause = f"LIMIT {limit}" if limit else ""
    rows = db.execute(text(sql.format(limit_clause=clause))).fetchall()
    return [r[0] for r in rows]


def _fetch_web_places(db: Session, limit: Optional[int]) -> List[str]:
    """Any active place with website but no menu (excludes already-queued providers)."""
    sql = """
        SELECT p.id
        FROM places p
        LEFT JOIN (
            SELECT place_id, COUNT(*) AS cnt
            FROM menu_items
            GROUP BY place_id
        ) mi ON mi.place_id = p.id
        WHERE p.is_active = true
          AND p.website IS NOT NULL
          AND p.website != ''
          AND (mi.cnt IS NULL OR mi.cnt = 0)
          AND p.website NOT LIKE '%toasttab.com%'
          AND p.website NOT LIKE '%chownow.com%'
          AND p.website NOT LIKE '%clover.com%'
          AND p.website NOT LIKE '%squareup.com%'
          AND p.website NOT LIKE '%popmenu.com%'
          AND (p.grubhub_url IS NULL OR p.grubhub_url = '')
        ORDER BY p.master_score DESC
        {limit_clause}
    """
    clause = f"LIMIT {limit}" if limit else ""
    rows = db.execute(text(sql.format(limit_clause=clause))).fetchall()
    return [r[0] for r in rows]


def _build_place_id_list(
    db: Session,
    priority: str,
    limit: Optional[int],
) -> List[str]:
    seen: set = set()
    out: List[str] = []

    def _add(ids: List[str]):
        for pid in ids:
            if pid not in seen:
                seen.add(pid)
                out.append(pid)

    per_bucket = limit  # apply limit per bucket when mode is all; final trim below

    if priority == "smart":
        selector = SmartTargetSelector()
        result = selector.select(db, limit=limit)

        # Print selection report before extraction starts
        print(f"\n  SMART MODE — scoring {result.total_candidates} candidates", flush=True)
        print(f"  Selected: {len(result.selected)}  Skipped: {len(result.skipped)}", flush=True)

        if result.skipped:
            # Summarize skip reasons
            skip_counts: dict = {}
            for t in result.skipped:
                skip_counts[t.skipped_reason or "unknown"] = skip_counts.get(t.skipped_reason or "unknown", 0) + 1
            print("  Skip reasons:", flush=True)
            for reason, count in sorted(skip_counts.items(), key=lambda x: -x[1]):
                print(f"    {reason:<30} {count:>5}", flush=True)

        if result.selected:
            print("\n  TOP 20 SELECTED TARGETS:", flush=True)
            print(f"  {'Score':>5}  {'Name':<40}  {'Strategy':<22}  {'Reason'}", flush=True)
            print(f"  {'-'*5}  {'-'*40}  {'-'*22}  {'-'*30}", flush=True)
            for t in result.selected[:20]:
                print(
                    f"  {t.target_score:>5}  {t.name[:40]:<40}  "
                    f"{t.recommended_strategy:<22}  {t.selected_reason}",
                    flush=True,
                )
        print(flush=True)

        return [t.place_id for t in result.selected]

    if priority in ("grubhub", "all"):
        _add(_fetch_grubhub_places(db, per_bucket))

    if priority in ("provider", "providers", "all"):
        _add(_fetch_provider_places(db, per_bucket))

    if priority in ("web", "all"):
        _add(_fetch_web_places(db, per_bucket))

    if limit:
        out = out[:limit]

    return out


# =========================================================
# STATS TRACKER
# =========================================================

@dataclass
class BatchStats:
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    fallback_used: int = 0
    total_items_added: int = 0
    total_images_bridged: int = 0
    errors: List[str] = field(default_factory=list)

    # Strategy breakdown
    by_strategy: dict = field(default_factory=lambda: {
        "direct_request": {"tried": 0, "ok": 0, "fail": 0},
        "structured_request": {"tried": 0, "ok": 0, "fail": 0},
        "playwright_render": {"tried": 0, "ok": 0, "fail": 0},
        "authenticated_fetch": {"tried": 0, "ok": 0, "fail": 0},
        "fail_fast": {"tried": 0, "ok": 0, "fail": 0},
        "none": {"tried": 0, "ok": 0, "fail": 0},
    })
    by_blocked_reason: dict = field(default_factory=dict)

    @property
    def success_rate(self) -> float:
        return (self.succeeded / self.total * 100) if self.total else 0.0

    @property
    def failure_rate(self) -> float:
        return (self.failed / self.total * 100) if self.total else 0.0

    @property
    def avg_items(self) -> float:
        return (self.total_items_added / self.succeeded) if self.succeeded else 0.0

    def record_strategy(self, strategy: Optional[str], succeeded: bool):
        key = strategy or "none"
        bucket = self.by_strategy.setdefault(key, {"tried": 0, "ok": 0, "fail": 0})
        bucket["tried"] += 1
        if succeeded:
            bucket["ok"] += 1
        else:
            bucket["fail"] += 1

    def record_blocked(self, reason: Optional[str]):
        if reason:
            self.by_blocked_reason[reason] = self.by_blocked_reason.get(reason, 0) + 1


# =========================================================
# MAIN
# =========================================================

def main(argv: Optional[List[str]] = None):
    parser = argparse.ArgumentParser(description="Phase 4 batch extractor")
    parser.add_argument("--limit", type=int, default=None, help="Max places to process")
    parser.add_argument(
        "--priority",
        choices=["grubhub", "provider", "providers", "web", "all", "smart"],
        default="all",
        help="Which source bucket to target (smart = score-ranked, skips blocked)",
    )
    parser.add_argument(
        "--run",
        action="store_true",
        help=(
            "Actually execute. Without this, prints the target count and a "
            "sample of place IDs/names and exits -- same discipline as "
            "run_menu_backlog_canary.py, so a batch run is never the first "
            "thing that happens by accident."
        ),
    )
    args = parser.parse_args(argv)

    if args.limit is None or args.limit > MAX_BATCH_SIZE:
        print(
            f"Refused: --limit is required and must be <= {MAX_BATCH_SIZE} "
            f"(got {args.limit!r}). This script writes menu_items through a "
            f"less-guarded extraction path (ExtractionController, not "
            f"menu_extraction_router.py's ranker/entity checks) -- run it in "
            f"smaller batches and spot-check results between runs.",
            file=sys.stderr,
        )
        return 2

    db = SessionLocal()

    try:
        # ── Build target list ─────────────────────────────────────────
        print("Building target list...", flush=True)
        place_ids = _build_place_id_list(db, priority=args.priority, limit=args.limit)
        total = len(place_ids)

        if total == 0:
            print("No places need menus — nothing to do.")
            return

        print(f"Targets: {total}  priority={args.priority}  limit={args.limit or 'none'}", flush=True)

        if not args.run:
            print("Preview only (pass --run to execute). Sample targets:", flush=True)
            for pid in place_ids[:10]:
                place = db.query(Place).filter(Place.id == pid).first()
                name = getattr(place, "name", None) or "?"
                print(f"  {pid}  {name}", flush=True)
            if total > 10:
                print(f"  ... and {total - 10} more", flush=True)
            return

        print("=" * 70, flush=True)

        orchestrator = MasterDataOrchestrator()
        stats = BatchStats(total=total)

        start_time = time.time()

        for i, place_id in enumerate(place_ids, 1):
            # Load place ORM object
            place = db.query(Place).filter(Place.id == place_id).first()

            if not place:
                stats.failed += 1
                stats.errors.append(f"{place_id}: place not found in DB")
                continue

            try:
                result: MasterDataResult = orchestrator.ensure_place(db=db, place=place)

                items_added = result.menu_items_after - result.menu_items_before
                succeeded = result.menu_action in ("extracted", "fallback")

                if succeeded:
                    stats.succeeded += 1
                    stats.total_items_added += max(items_added, 0)
                elif result.menu_action == "skipped":
                    stats.skipped += 1
                else:
                    stats.failed += 1

                if result.menu_fallback_used:
                    stats.fallback_used += 1

                stats.total_images_bridged += result.item_images_bridged

                # Record strategy from orchestrator result
                strategy_used = getattr(result, "menu_strategy", None)
                blocked_reason = getattr(result, "menu_blocked_reason", None)
                stats.record_strategy(strategy_used, succeeded)
                if blocked_reason:
                    stats.record_blocked(blocked_reason)

                # Per-place log line
                status_char = {
                    "extracted": "✓",
                    "fallback":  "~",
                    "skipped":   "-",
                    "failed":    "✗",
                    "none":      "?",
                }.get(result.menu_action, "?")

                name_display = (getattr(place, "name", None) or place_id)[:40]
                strategy_tag = result.menu_strategy or "?"
                failure_tag = ""
                if result.menu_blocked_reason:
                    failure_tag = f"  BLOCKED:{result.menu_blocked_reason}"
                elif getattr(result, "failure_reason", None) and result.menu_action == "failed":
                    failure_tag = f"  FAIL:{result.failure_reason}"

                selected_url = getattr(result, "source_selected", None)
                url_tag = f"  URL:{selected_url[:40]}" if selected_url else ""

                print(
                    f"  [{i:>5}/{total}] {status_char} "
                    f"{name_display:<40}  "
                    f"action={result.menu_action:<10}  "
                    f"strategy={strategy_tag:<20}  "
                    f"items_added={max(items_added, 0):>4}  "
                    f"img={result.image_action:<10}"
                    f"{failure_tag}{url_tag}",
                    flush=True,
                )

                if result.errors:
                    for err in result.errors:
                        print(f"         ERR: {err}", flush=True)
                    stats.errors.extend([f"{place_id}: {e}" for e in result.errors])

            except Exception as exc:
                stats.failed += 1
                stats.errors.append(f"{place_id}: exception — {exc}")
                print(f"  [{i:>5}/{total}] ✗ {place_id}  EXCEPTION: {exc}", flush=True)
                logger.exception("batch_place_exception place_id=%s", place_id)

            # Progress checkpoint every 50 places
            if i % 50 == 0:
                elapsed = time.time() - start_time
                rate = i / elapsed if elapsed > 0 else 0
                eta = (total - i) / rate if rate > 0 else 0
                print(
                    f"\n  --- checkpoint {i}/{total}  "
                    f"ok={stats.succeeded}  fail={stats.failed}  skip={stats.skipped}  "
                    f"items={stats.total_items_added}  "
                    f"elapsed={elapsed:.0f}s  eta={eta:.0f}s ---\n",
                    flush=True,
                )

            # Commit periodically to avoid holding huge transactions
            if i % 10 == 0:
                try:
                    db.commit()
                except Exception as exc:
                    logger.warning("batch_commit_failed error=%s", exc)
                    db.rollback()

        # Final commit
        try:
            db.commit()
        except Exception as exc:
            logger.warning("batch_final_commit_failed error=%s", exc)
            db.rollback()

        elapsed_total = time.time() - start_time

        # ── Aggregate stats ───────────────────────────────────────────
        print("\n" + "=" * 70, flush=True)
        print("PHASE 4 BATCH COMPLETE", flush=True)
        print("=" * 70, flush=True)
        print(f"  Total processed:   {total:>6}", flush=True)
        print(f"  Succeeded:         {stats.succeeded:>6}  ({stats.success_rate:.1f}%)", flush=True)
        print(f"  Failed:            {stats.failed:>6}  ({stats.failure_rate:.1f}%)", flush=True)
        print(f"  Skipped (had menu):{stats.skipped:>6}", flush=True)
        print(f"  Fallback used:     {stats.fallback_used:>6}", flush=True)
        print(f"  Total items added: {stats.total_items_added:>6}", flush=True)
        print(f"  Avg items/success: {stats.avg_items:>6.1f}", flush=True)
        print(f"  Item images bridged:{stats.total_images_bridged:>5}", flush=True)
        print(f"  Elapsed:           {elapsed_total:.0f}s", flush=True)

        # Final DB counts
        row = db.execute(text("SELECT COUNT(*) FROM menu_items")).fetchone()
        total_menu_items = row[0] if row else 0

        row = db.execute(text("SELECT COUNT(DISTINCT place_id) FROM menu_items")).fetchone()
        places_with_menu = row[0] if row else 0

        row = db.execute(text("SELECT COUNT(*) FROM places WHERE is_active = true")).fetchone()
        active_places = row[0] if row else 0

        coverage = (places_with_menu / active_places * 100) if active_places else 0

        print(f"\n  DB AFTER BATCH:", flush=True)
        print(f"    menu_items total:     {total_menu_items:>8,}", flush=True)
        print(f"    places with menus:    {places_with_menu:>8,} / {active_places:,}  ({coverage:.1f}%)", flush=True)

        # Strategy breakdown
        active_strategies = {
            k: v for k, v in stats.by_strategy.items() if v["tried"] > 0
        }
        if active_strategies:
            print(f"\n  STRATEGY BREAKDOWN:", flush=True)
            for strat, counts in active_strategies.items():
                ok_pct = (counts["ok"] / counts["tried"] * 100) if counts["tried"] else 0
                print(
                    f"    {strat:<22} tried={counts['tried']:>4}  "
                    f"ok={counts['ok']:>4}  fail={counts['fail']:>4}  "
                    f"({ok_pct:.0f}% success)",
                    flush=True,
                )

        if stats.by_blocked_reason:
            print(f"\n  BLOCKED REASONS:", flush=True)
            for reason, count in sorted(stats.by_blocked_reason.items(), key=lambda x: -x[1]):
                print(f"    {reason:<30} {count:>5}", flush=True)

        if stats.errors:
            print(f"\n  ERRORS ({len(stats.errors)}):", flush=True)
            for err in stats.errors[:20]:
                print(f"    {err}", flush=True)
            if len(stats.errors) > 20:
                print(f"    ... and {len(stats.errors) - 20} more", flush=True)

        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
