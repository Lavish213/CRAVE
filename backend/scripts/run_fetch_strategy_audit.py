"""
Fetch Strategy Audit — CRAVE Phase 4

Classifies all places needing menus by fetch strategy BEFORE running extraction.
Shows exactly what's blocked, why, and what CAN run.

Run:
    cd backend
    python scripts/run_fetch_strategy_audit.py
"""
from __future__ import annotations

import sys

sys.path.insert(0, ".")

from sqlalchemy import text
from app.db.session import SessionLocal
from app.services.menu.fetch.fetch_strategy_router import (
    FetchStrategyRouter,
    STRATEGY_DIRECT,
    STRATEGY_STRUCTURED,
    STRATEGY_PLAYWRIGHT,
    STRATEGY_AUTH,
    STRATEGY_FAIL_FAST,
)


def main():
    db = SessionLocal()
    router = FetchStrategyRouter()

    try:
        # All active places without menus that have a website
        rows = db.execute(text("""
            SELECT p.id, p.name, p.website, p.grubhub_url
            FROM places p
            LEFT JOIN (
                SELECT place_id, COUNT(*) AS cnt
                FROM menu_items GROUP BY place_id
            ) mi ON mi.place_id = p.id
            WHERE p.is_active = true
              AND (p.website IS NOT NULL OR p.grubhub_url IS NOT NULL)
              AND (mi.cnt IS NULL OR mi.cnt = 0)
            ORDER BY p.master_score DESC
        """)).fetchall()

        total = len(rows)
        print(f"Places needing menus with URLs: {total:,}")
        print()

        # Classify each
        by_strategy: dict[str, list] = {
            STRATEGY_DIRECT: [],
            STRATEGY_STRUCTURED: [],
            STRATEGY_PLAYWRIGHT: [],
            STRATEGY_AUTH: [],
            STRATEGY_FAIL_FAST: [],
        }
        by_blocked: dict[str, int] = {}

        for place_id, name, website, grubhub_url in rows:
            url = website or grubhub_url or ""
            if not url:
                continue
            result = router.classify(url)
            by_strategy.setdefault(result.strategy, []).append({
                "place_id": place_id,
                "name": name,
                "url": url,
                "blocked_reason": result.blocked_reason,
                "needs_auth": result.needs_auth,
                "needs_browser": result.needs_browser,
                "notes": result.notes,
            })
            if result.blocked_reason:
                by_blocked[result.blocked_reason] = by_blocked.get(result.blocked_reason, 0) + 1

        # ── Report ─────────────────────────────────────────────────
        print("=" * 65)
        print("  FETCH STRATEGY MATRIX")
        print("=" * 65)

        strategy_labels = {
            STRATEGY_DIRECT: "direct_request      (plain HTTPX, can run now)",
            STRATEGY_STRUCTURED: "structured_request  (API-mode headers, can run now)",
            STRATEGY_PLAYWRIGHT: "playwright_render    (headless browser, can run now)",
            STRATEGY_AUTH: "authenticated_fetch  (needs GRUBHUB_COOKIES)",
            STRATEGY_FAIL_FAST: "fail_fast            (blocked, skip)",
        }

        for strategy, label in strategy_labels.items():
            places = by_strategy.get(strategy, [])
            print(f"\n  {label}")
            print(f"  Count: {len(places):,}")
            for p in places[:5]:
                reason = f"  [{p['blocked_reason']}]" if p["blocked_reason"] else ""
                print(f"    {p['name'][:40]:<40} {p['url'][:60]}{reason}")
            if len(places) > 5:
                print(f"    ... and {len(places) - 5} more")

        print("\n" + "=" * 65)
        print("  BLOCKED REASON BREAKDOWN")
        print("=" * 65)
        for reason, count in sorted(by_blocked.items(), key=lambda x: -x[1]):
            print(f"  {reason:<35} {count:>6,}")

        print("\n" + "=" * 65)
        print("  ACTION PLAN")
        print("=" * 65)

        runnable = (
            len(by_strategy.get(STRATEGY_DIRECT, []))
            + len(by_strategy.get(STRATEGY_STRUCTURED, []))
            + len(by_strategy.get(STRATEGY_PLAYWRIGHT, []))
        )
        auth_blocked = len(by_strategy.get(STRATEGY_AUTH, []))
        other_blocked = sum(
            len(v) for k, v in by_strategy.items()
            if k == STRATEGY_FAIL_FAST
        ) - auth_blocked

        print(f"  Runnable now:         {runnable:>6,}")
        print(f"  Blocked (auth):       {auth_blocked:>6,}  → run grab_grubhub_cookies.py")
        print(f"  Blocked (other):      {other_blocked:>6,}  → aggregators/redirect traps")
        print(f"  Total:                {total:>6,}")

        playwright_avail = router._check_playwright()
        print(f"\n  Playwright installed: {playwright_avail}")
        if not playwright_avail:
            print("  → python -m playwright install chromium")

        import os
        gh_creds = bool(os.environ.get("GRUBHUB_COOKIES", "").strip())
        print(f"  Grubhub credentials: {gh_creds}")
        if not gh_creds:
            print("  → python scripts/grab_grubhub_cookies.py")

        print()

    finally:
        db.close()


if __name__ == "__main__":
    main()
