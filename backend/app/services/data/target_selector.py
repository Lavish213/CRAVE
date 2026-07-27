"""
SmartTargetSelector — Phase 4

Scores and ranks extraction candidates by probability of producing real menu items.
Skips known-blocked sources. Prioritizes high-yield providers.

Score formula (additive):
    +100  grubhub_url + GRUBHUB_COOKIES present
    +80   popmenu
    +75   square.site / squareup.com
    +70   chownow
    +70   clover
    +50   website path contains /menu
    +40   website path contains /order
    +30   normal restaurant website
    +20   price_tier <= 2 (local/indie restaurant)
    +15   website present but no high-value signal (generic)

    -80   toasttab.com (known captcha/blocked)
    -100  delivery aggregators (doordash, ubereats, etc.)
    -60   redirect traps (opentable, resy, tock, michelin, yelp, tripadvisor)
    -30   known chain/corporate page patterns
    -100  missing_auth (grubhub URL but no cookies)

Skip if statically classified as: blocked_provider, missing_auth, redirect_trap, dead_site.

Usage:
    from app.services.data.target_selector import SmartTargetSelector
    selector = SmartTargetSelector()
    selected, skipped = selector.select(db, limit=100)
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.menu.fetch.fetch_strategy_router import (
    classify_fetch_strategy,
    STRATEGY_FAIL_FAST,
    STRATEGY_AUTH,
)

logger = logging.getLogger(__name__)


# =========================================================
# SCORING CONSTANTS
# =========================================================

# Additive bonuses
SCORE_GRUBHUB_AUTH       = 100
SCORE_POPMENU            = 80
SCORE_SQUARE             = 75
SCORE_CHOWNOW            = 70
SCORE_CLOVER             = 70
SCORE_URL_HAS_MENU       = 50
SCORE_URL_HAS_ORDER      = 40
SCORE_HAS_WEBSITE        = 30
SCORE_LOCAL_TIER         = 20
SCORE_GENERIC_WEBSITE    = 15

# Penalties
PENALTY_TOASTTAB         = -80
PENALTY_AGGREGATOR       = -100
PENALTY_REDIRECT_TRAP    = -60
PENALTY_CHAIN_PAGE       = -30
PENALTY_MISSING_AUTH     = -100

# Static skip reasons (place excluded from selected list)
_SKIP_REASONS = frozenset({
    "blocked_provider",
    "missing_auth",
    "redirect_trap",
    "dead_site",
    "captcha_block",
    "cloudflare_block",
})

# Domain pattern sets
_AGGREGATOR_DOMAINS = frozenset({"doordash.com", "ubereats.com", "postmates.com", "seamless.com", "caviar.com"})
_REDIRECT_TRAP_DOMAINS = frozenset({"opentable.com", "resy.com", "tock.com", "michelin.com", "yelp.com", "tripadvisor.com"})
_CHAIN_PATTERNS = ("locations.", "/locations/", "locations.com", "findus.", "storelocator")

# Cooldown: hours before a statically-blocked place can be retried
# (only applies to places that pass static check but have session failure)
BLOCK_COOLDOWN_HOURS = 48


# =========================================================
# RESULT TYPES
# =========================================================

@dataclass
class TargetScore:
    place_id: str
    name: str
    website: Optional[str]
    grubhub_url: Optional[str]
    target_score: int
    selected_reason: str
    skipped_reason: Optional[str]        # None = selected, else = why skipped
    recommended_strategy: str

    @property
    def is_selected(self) -> bool:
        return self.skipped_reason is None


@dataclass
class SelectionResult:
    selected: List[TargetScore] = field(default_factory=list)
    skipped: List[TargetScore] = field(default_factory=list)
    total_candidates: int = 0

    def summary(self) -> str:
        lines = [
            f"Candidates:  {self.total_candidates}",
            f"Selected:    {len(self.selected)}",
            f"Skipped:     {len(self.skipped)}",
        ]
        if self.selected:
            top = self.selected[:5]
            lines.append("Top 5:")
            for t in top:
                lines.append(
                    f"  [{t.target_score:>4}] {t.name[:40]:<40}  "
                    f"strategy={t.recommended_strategy}  "
                    f"reason={t.selected_reason}"
                )
        return "\n".join(lines)


# =========================================================
# SELECTOR
# =========================================================

class SmartTargetSelector:
    """
    Ranks extraction candidates by expected menu yield.

    select() returns a SelectionResult with selected (scored, sorted DESC)
    and skipped (excluded, with reason) lists.
    """

    def select(
        self,
        db: Session,
        limit: Optional[int] = None,
        include_skipped_in_output: bool = True,
    ) -> SelectionResult:
        """
        Load candidates, score, filter, sort.

        Args:
            db:                       SQLAlchemy session
            limit:                    Max selected targets to return
            include_skipped_in_output: Whether to populate result.skipped
        """
        rows = self._load_candidates(db)
        result = SelectionResult(total_candidates=len(rows))

        for row in rows:
            scored = self._score_row(row)
            if scored.is_selected:
                result.selected.append(scored)
            elif include_skipped_in_output:
                result.skipped.append(scored)

        # Sort selected: score DESC, then name for determinism
        result.selected.sort(key=lambda t: (-t.target_score, t.name))

        if limit:
            result.selected = result.selected[:limit]

        logger.info(
            "smart_target_selector.done candidates=%s selected=%s skipped=%s limit=%s",
            result.total_candidates,
            len(result.selected),
            len(result.skipped),
            limit,
        )

        return result

    # =========================================================
    # LOAD
    # =========================================================

    def _load_candidates(self, db: Session) -> list:
        """Load all active places without menu items."""
        sql = """
            SELECT
                p.id,
                p.name,
                p.website,
                p.grubhub_url,
                p.master_score,
                p.price_tier
            FROM places p
            LEFT JOIN (
                SELECT place_id, COUNT(*) AS cnt
                FROM menu_items
                GROUP BY place_id
            ) mi ON mi.place_id = p.id
            WHERE p.is_active = 1
              AND (mi.cnt IS NULL OR mi.cnt = 0)
            ORDER BY p.master_score DESC
        """
        return db.execute(text(sql)).fetchall()

    # =========================================================
    # SCORE
    # =========================================================

    def _score_row(self, row) -> TargetScore:
        """Score a single candidate row."""
        place_id = row[0]
        name     = row[1] or ""
        website  = (row[2] or "").strip()
        gh_url   = (row[3] or "").strip()
        price_tier = row[5]

        score, reasons, skip_reason = self._compute_score(
            website=website,
            grubhub_url=gh_url,
            price_tier=price_tier,
        )

        strategy = self._recommend_strategy(
            website=website,
            grubhub_url=gh_url,
            skip_reason=skip_reason,
        )

        return TargetScore(
            place_id=place_id,
            name=name,
            website=website or None,
            grubhub_url=gh_url or None,
            target_score=score,
            selected_reason=reasons,
            skipped_reason=skip_reason,
            recommended_strategy=strategy,
        )

    def _compute_score(
        self,
        *,
        website: str,
        grubhub_url: str,
        price_tier: Optional[int],
    ) -> Tuple[int, str, Optional[str]]:
        """
        Returns (score, selected_reason, skip_reason).
        skip_reason is None if place should be selected.
        """
        score = 0
        reasons: List[str] = []
        skip_reason: Optional[str] = None

        url = website.lower()
        gh  = grubhub_url.lower()

        # ── No extractable URL at all ──────────────────────────
        if not url and not gh:
            return 0, "no_url", "dead_site"

        # ── Grubhub ───────────────────────────────────────────
        if gh:
            has_creds = bool(os.environ.get("GRUBHUB_COOKIES", "").strip())
            if has_creds:
                score += SCORE_GRUBHUB_AUTH
                reasons.append("grubhub+auth")
            else:
                score += PENALTY_MISSING_AUTH
                return score, "grubhub_no_cookies", "missing_auth"

        if url:
            # ── Delivery aggregators: hard skip ────────────────
            for domain in _AGGREGATOR_DOMAINS:
                if domain in url:
                    score += PENALTY_AGGREGATOR
                    return score, f"aggregator:{domain}", "blocked_provider"

            # ── Redirect traps: hard skip ──────────────────────
            for domain in _REDIRECT_TRAP_DOMAINS:
                if domain in url:
                    score += PENALTY_REDIRECT_TRAP
                    return score, f"redirect_trap:{domain}", "redirect_trap"

            # ── Toast: known captcha/blocked ───────────────────
            if "toasttab" in url:
                score += PENALTY_TOASTTAB
                return score, "toasttab_blocked", "blocked_provider"

            # ── Provider bonuses ───────────────────────────────
            if "popmenu" in url:
                score += SCORE_POPMENU
                reasons.append("popmenu")
            elif "square.site" in url or "squareup.com" in url:
                score += SCORE_SQUARE
                reasons.append("square")
            elif "chownow" in url:
                score += SCORE_CHOWNOW
                reasons.append("chownow")
            elif "clover" in url:
                score += SCORE_CLOVER
                reasons.append("clover")

            # ── URL path signals ───────────────────────────────
            if "/menu" in url:
                score += SCORE_URL_HAS_MENU
                reasons.append("url_has_menu")
            elif "/order" in url:
                score += SCORE_URL_HAS_ORDER
                reasons.append("url_has_order")
            elif reasons:
                # Provider already scored — base website credit
                score += SCORE_HAS_WEBSITE
                reasons.append("provider_site")
            else:
                score += SCORE_GENERIC_WEBSITE
                reasons.append("generic_website")

            # ── Chain/corporate page signal ────────────────────
            for pat in _CHAIN_PATTERNS:
                if pat in url:
                    score += PENALTY_CHAIN_PAGE
                    reasons.append("chain_page")
                    break

        # ── Price tier bonus ───────────────────────────────────
        if price_tier is not None and price_tier <= 2:
            score += SCORE_LOCAL_TIER
            reasons.append("local_tier")

        return score, ", ".join(reasons) or "scored", skip_reason

    def _recommend_strategy(
        self,
        *,
        website: str,
        grubhub_url: str,
        skip_reason: Optional[str],
    ) -> str:
        if skip_reason:
            return f"skip:{skip_reason}"

        if grubhub_url:
            return "authenticated_fetch"

        if not website:
            return "no_url"

        try:
            strategy = classify_fetch_strategy(website)
            return strategy.strategy
        except Exception:
            return "direct_request"


# =========================================================
# MODULE-LEVEL CONVENIENCE
# =========================================================

_selector = SmartTargetSelector()


def select_targets(
    db: Session,
    limit: Optional[int] = None,
) -> SelectionResult:
    """Module-level convenience wrapper."""
    return _selector.select(db, limit=limit)
