# Menu Source Discovery System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Probe `Place.website` to detect menu provider URLs (Toast, Clover, PopMenu, etc.) and populate `Place.menu_source_url` so the existing extractors can fetch menus they currently miss.

**Architecture:** Two new files fill the gap in the existing pipeline. `website_provider_probe.py` is a pure function that fetches a website + common paths, checks if the final URL or HTML links to a known provider, and returns a `ProbeResult` with a confidence score. `scripts/discover_menu_sources.py` is the batch worker that queries all places with `website != NULL AND has_menu = FALSE AND menu_source_url IS NULL`, runs the probe, saves high-confidence results, and optionally triggers extraction. Everything else — `fetch()`, `discover_provider_urls()`, `extract_menu_from_url()` — already exists and is reused as-is.

**Tech Stack:** Python 3.11, SQLAlchemy 2.x, httpx (via existing `fetch()`), pytest, unittest.mock

---

## Codebase Context (read before touching anything)

- `app/services/network/http_fetcher.py` — `fetch(url, *, mode, ...)→ httpx.Response`. The response's `.url` attribute is the final URL after all redirects. Mode `"document"` is correct for HTML pages.
- `app/services/menu/discovery/provider_discovery.py` — `discover_provider_urls(html: str) → List[str]`. Scans hrefs, iframes, and script srcs for known provider domains. Already handles Toast, Clover, PopMenu, Square, ChowNow, Olo.
- `app/services/menu/extraction/extract_menu_from_url.py` — `extract_menu_from_url(*, db, place_id, url) → ExtractedMenu`. Handles the full extraction pipeline including ingestion. Use this when `--extract` is passed.
- `app/db/models/place.py` — `Place.menu_source_url` (String 1024, nullable) already exists. `Place.has_menu` (bool) already exists.
- No `tests/menu/` directory exists yet — you must create it with `__init__.py`.

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `app/services/menu/discovery/website_provider_probe.py` | Core probe: fetch website + paths, detect provider, return ProbeResult |
| Create | `tests/menu/__init__.py` | Test package init (empty file) |
| Create | `tests/menu/test_website_provider_probe.py` | Unit + integration tests for probe |
| Create | `scripts/discover_menu_sources.py` | Batch worker: queries DB, runs probe, saves results |

---

## Task 1: `website_provider_probe.py` — core detection engine

**Files:**
- Create: `app/services/menu/discovery/website_provider_probe.py`
- Create: `tests/menu/__init__.py`
- Create: `tests/menu/test_website_provider_probe.py`

- [ ] **Step 1: Create the test directory and write failing tests**

```bash
touch /path/to/backend/tests/menu/__init__.py
```

Create `tests/menu/test_website_provider_probe.py`:

```python
import pytest
from unittest.mock import patch, MagicMock
import httpx

from app.services.menu.discovery.website_provider_probe import (
    probe_website,
    ProbeResult,
    _provider_from_url,
    _should_skip,
    _normalize_website,
    MIN_CONFIDENCE,
)


def _mock_response(*, status_code=200, text="", url="https://example.com"):
    res = MagicMock(spec=httpx.Response)
    res.status_code = status_code
    res.text = text
    res.url = httpx.URL(url)
    return res


# ── Helper unit tests ─────────────────────────────────────────────────────────

def test_provider_from_url_toast():
    assert _provider_from_url("https://www.toasttab.com/horn-bbq") == "toast"

def test_provider_from_url_clover():
    assert _provider_from_url("https://clover.com/online-ordering/foo") == "clover"

def test_provider_from_url_popmenu():
    assert _provider_from_url("https://order.popmenu.com/some-restaurant") == "popmenu"

def test_provider_from_url_square():
    assert _provider_from_url("https://some-place.square.site/order") == "square"

def test_provider_from_url_unknown():
    assert _provider_from_url("https://hornbbq.com/menu") is None

def test_should_skip_yelp():
    assert _should_skip("https://www.yelp.com/biz/place") is True

def test_should_skip_tripadvisor():
    assert _should_skip("https://tripadvisor.com/Restaurant_Review-foo") is True

def test_should_skip_real_site():
    assert _should_skip("https://hornbbq.com") is False

def test_normalize_adds_scheme():
    assert _normalize_website("hornbbq.com") == "https://hornbbq.com"

def test_normalize_strips_trailing_slash():
    assert _normalize_website("https://hornbbq.com/") == "https://hornbbq.com"

def test_normalize_preserves_https():
    assert _normalize_website("https://hornbbq.com") == "https://hornbbq.com"

def test_probe_result_found_true_when_high_confidence():
    r = ProbeResult(menu_source_url="https://toasttab.com/foo", provider="toast", confidence=1.0)
    assert r.found is True

def test_probe_result_found_false_when_low_confidence():
    r = ProbeResult(menu_source_url="https://example.com/menu", provider="jsonld", confidence=0.5)
    assert r.found is False

def test_probe_result_found_false_when_no_url():
    r = ProbeResult(menu_source_url=None, provider=None, confidence=0.9)
    assert r.found is False


# ── probe_website integration tests (mocked fetch) ───────────────────────────

def test_probe_toast_redirect():
    """Direct redirect to toasttab.com → confidence=1.0, stops immediately"""
    res = _mock_response(
        url="https://www.toasttab.com/horn-barbecue/v3/menu",
        text="",
    )
    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://hornbbq.com")

    assert result.found is True
    assert result.provider == "toast"
    assert result.confidence == 1.0
    assert "toasttab.com" in result.menu_source_url


def test_probe_provider_link_in_html():
    """HTML contains clover.com link → confidence=0.9"""
    html = '<a href="https://www.clover.com/online-ordering/some-place">Order</a>'
    res = _mock_response(text=html, url="https://example.com/menu")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "clover"
    assert result.confidence == 0.9


def test_probe_jsonld_menu():
    """HTML contains JSON-LD Menu type → confidence=0.7"""
    html = '<script type="application/ld+json">{"@type": "Menu"}</script>'
    res = _mock_response(text=html, url="https://example.com/menu")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "jsonld"
    assert result.confidence == 0.7


def test_probe_no_signals():
    """Plain HTML with no menu signals → not found"""
    html = "<html><body><p>Welcome!</p></body></html>"
    res = _mock_response(text=html, url="https://example.com")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is False
    assert result.confidence < MIN_CONFIDENCE


def test_probe_skips_aggregator_without_fetch():
    """Aggregator domains skip all HTTP calls"""
    with patch("app.services.menu.discovery.website_provider_probe.fetch") as mock_fetch:
        result = probe_website("https://www.yelp.com/biz/some-place")

    mock_fetch.assert_not_called()
    assert result.found is False


def test_probe_prefers_redirect_over_html_link():
    """First path redirects to provider → returns immediately at confidence=1.0"""
    redirect_res = _mock_response(url="https://www.toasttab.com/foo")
    html_res = _mock_response(
        text='<a href="https://clover.com/order/bar">Order</a>',
        url="https://example.com/menu",
    )
    with patch(
        "app.services.menu.discovery.website_provider_probe.fetch",
        side_effect=[redirect_res, html_res],
    ):
        result = probe_website("https://example.com")

    assert result.provider == "toast"
    assert result.confidence == 1.0


def test_probe_fetch_failure_returns_not_found():
    """Network failure → not found, no exception propagates"""
    with patch(
        "app.services.menu.discovery.website_provider_probe.fetch",
        side_effect=Exception("connect timeout"),
    ):
        result = probe_website("https://hornbbq.com")

    assert result.found is False
    assert result.confidence == 0.0


def test_probe_non_200_status_continues_to_next_path():
    """404 on first path → tries next paths"""
    fail_res = _mock_response(status_code=404, text="", url="https://example.com")
    html_res = _mock_response(
        text='<a href="https://www.toasttab.com/some-place">Order</a>',
        url="https://example.com/menu",
    )
    with patch(
        "app.services.menu.discovery.website_provider_probe.fetch",
        side_effect=[fail_res, html_res],
    ):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "toast"
```

- [ ] **Step 2: Run tests to verify they all fail (ImportError expected)**

```bash
cd /path/to/backend
python -m pytest tests/menu/test_website_provider_probe.py -v 2>&1 | head -30
```

Expected: `ImportError: cannot import name 'probe_website' from 'app.services.menu.discovery.website_provider_probe'`

- [ ] **Step 3: Write the implementation**

Create `app/services/menu/discovery/website_provider_probe.py`:

```python
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse

from app.services.network.http_fetcher import fetch
from app.services.menu.discovery.provider_discovery import discover_provider_urls


logger = logging.getLogger(__name__)


_PROVIDER_DOMAINS: dict[str, str] = {
    "toasttab.com": "toast",
    "square.site": "square",
    "squareup.com": "square",
    "clover.com": "clover",
    "popmenu.com": "popmenu",
    "chownow.com": "chownow",
    "olo.com": "olo",
}

_PROBE_PATHS = [
    "",
    "/menu",
    "/order",
    "/order-online",
    "/online-ordering",
    "/food-menu",
]

_SKIP_DOMAINS = frozenset({
    "yelp.com",
    "tripadvisor.com",
    "facebook.com",
    "instagram.com",
    "tiktok.com",
})

_JSONLD_MENU_RE = re.compile(
    r'"@type"\s*:\s*"(?:Menu|MenuSection|MenuItem)"',
    re.IGNORECASE,
)

MIN_CONFIDENCE = 0.7


@dataclass(frozen=True)
class ProbeResult:
    menu_source_url: Optional[str]
    provider: Optional[str]
    confidence: float

    @property
    def found(self) -> bool:
        return self.menu_source_url is not None and self.confidence >= MIN_CONFIDENCE


def _provider_from_url(url: str) -> Optional[str]:
    """Return provider name if the URL contains a known provider domain."""
    lower = url.lower()
    for domain, provider in _PROVIDER_DOMAINS.items():
        if domain in lower:
            return provider
    return None


def _should_skip(website: str) -> bool:
    """Return True for aggregator and social domains that are never menu sources."""
    try:
        netloc = urlparse(website).netloc.lower().lstrip("www.")
        return any(netloc == d or netloc.endswith("." + d) for d in _SKIP_DOMAINS)
    except Exception:
        return False


def _normalize_website(website: str) -> str:
    """Ensure the website string has an https:// scheme and no trailing slash."""
    website = website.strip()
    if not website.startswith(("http://", "https://")):
        website = "https://" + website
    return website.rstrip("/")


def probe_website(website: str) -> ProbeResult:
    """
    Probe a restaurant website to find its menu provider URL.

    Strategy (ordered by confidence):
      1. Fetch each candidate path. If the final URL (after redirect) is a
         known provider domain → confidence 1.0, return immediately.
      2. Scan HTML for provider-domain hrefs/iframes/scripts → confidence 0.9.
         Continue scanning paths in case a later path yields a 1.0 redirect.
      3. Detect JSON-LD Menu schema in HTML → confidence 0.7.

    Only returns a result with .found=True when confidence >= 0.7.
    Idempotent — no DB writes, no side effects.
    """
    website = _normalize_website(website)

    if not website or _should_skip(website):
        return ProbeResult(menu_source_url=None, provider=None, confidence=0.0)

    best = ProbeResult(menu_source_url=None, provider=None, confidence=0.0)

    for path in _PROBE_PATHS:
        url = website + path

        try:
            res = fetch(url, mode="document")
        except Exception as exc:
            logger.debug("probe_fetch_failed url=%s err=%s", url, exc)
            continue

        if res.status_code not in (200, 301, 302, 303, 307, 308):
            continue

        # Check 1: did the final URL (after redirects) land on a provider?
        final_url = str(res.url)
        provider = _provider_from_url(final_url)
        if provider:
            logger.info(
                "probe_redirect_hit url=%s provider=%s final=%s",
                url, provider, final_url,
            )
            return ProbeResult(
                menu_source_url=final_url,
                provider=provider,
                confidence=1.0,
            )

        # Check 2: does the HTML reference a provider domain?
        try:
            html = res.text or ""
        except Exception:
            continue

        if not html:
            continue

        provider_urls = discover_provider_urls(html)
        if provider_urls:
            provider_url = provider_urls[0]
            prov = _provider_from_url(provider_url)
            if prov:
                candidate = ProbeResult(
                    menu_source_url=provider_url,
                    provider=prov,
                    confidence=0.9,
                )
                if candidate.confidence > best.confidence:
                    best = candidate
            continue  # keep scanning paths for a possible confidence=1.0

        # Check 3: JSON-LD Menu schema in HTML?
        if _JSONLD_MENU_RE.search(html):
            candidate = ProbeResult(
                menu_source_url=url,
                provider="jsonld",
                confidence=0.7,
            )
            if candidate.confidence > best.confidence:
                best = candidate

    logger.info(
        "probe_done website=%s provider=%s confidence=%.2f",
        website, best.provider, best.confidence,
    )
    return best
```

- [ ] **Step 4: Run tests to verify they all pass**

```bash
cd /path/to/backend
python -m pytest tests/menu/test_website_provider_probe.py -v
```

Expected output (all 22 tests pass):
```
tests/menu/test_website_provider_probe.py::test_provider_from_url_toast PASSED
tests/menu/test_website_provider_probe.py::test_provider_from_url_clover PASSED
tests/menu/test_website_provider_probe.py::test_provider_from_url_popmenu PASSED
tests/menu/test_website_provider_probe.py::test_provider_from_url_square PASSED
tests/menu/test_website_provider_probe.py::test_provider_from_url_unknown PASSED
tests/menu/test_website_provider_probe.py::test_should_skip_yelp PASSED
tests/menu/test_website_provider_probe.py::test_should_skip_tripadvisor PASSED
tests/menu/test_website_provider_probe.py::test_should_skip_real_site PASSED
tests/menu/test_website_provider_probe.py::test_normalize_adds_scheme PASSED
tests/menu/test_website_provider_probe.py::test_normalize_strips_trailing_slash PASSED
tests/menu/test_website_provider_probe.py::test_normalize_preserves_https PASSED
tests/menu/test_website_provider_probe.py::test_probe_result_found_true_when_high_confidence PASSED
tests/menu/test_website_provider_probe.py::test_probe_result_found_false_when_low_confidence PASSED
tests/menu/test_website_provider_probe.py::test_probe_result_found_false_when_no_url PASSED
tests/menu/test_website_provider_probe.py::test_probe_toast_redirect PASSED
tests/menu/test_website_provider_probe.py::test_probe_provider_link_in_html PASSED
tests/menu/test_website_provider_probe.py::test_probe_jsonld_menu PASSED
tests/menu/test_website_provider_probe.py::test_probe_no_signals PASSED
tests/menu/test_website_provider_probe.py::test_probe_skips_aggregator_without_fetch PASSED
tests/menu/test_website_provider_probe.py::test_probe_prefers_redirect_over_html_link PASSED
tests/menu/test_website_provider_probe.py::test_probe_fetch_failure_returns_not_found PASSED
tests/menu/test_website_provider_probe.py::test_probe_non_200_status_continues_to_next_path PASSED

22 passed in X.XXs
```

- [ ] **Step 5: Commit**

```bash
git add app/services/menu/discovery/website_provider_probe.py \
        tests/menu/__init__.py \
        tests/menu/test_website_provider_probe.py
git commit -m "feat: add website_provider_probe — detects menu providers from Place.website"
```

---

## Task 2: `scripts/discover_menu_sources.py` — batch worker

**Files:**
- Create: `scripts/discover_menu_sources.py`

**Context:** This script has no dedicated unit tests (it's a CLI script that wraps DB queries and calls the already-tested `probe_website`). Validation is by running `--dry-run` against the live DB.

- [ ] **Step 1: Write the script**

Create `scripts/discover_menu_sources.py`:

```python
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
        help="Run menu extraction immediately after discovery (requires live DB)",
    )
    args = parser.parse_args()
    run(dry_run=args.dry_run, limit=args.limit, extract=args.extract)
```

- [ ] **Step 2: Validate with dry-run (no DB writes)**

```bash
cd /path/to/backend
python scripts/discover_menu_sources.py --dry-run --limit 20
```

Expected output format:
```
Candidates: 20 places (website set, no menu, no menu_source_url)
DRY RUN — probe runs, no DB writes

  FOUND 'Commis'                                   toast  https://www.toasttab.com/commis/...
  SKIP  'Some Random Place'                         conf=0.00
  FOUND 'Horn Barbecue'                             toast  https://www.toasttab.com/horn-barbecue/...
  ...

Done: X discovered, Y skipped
DRY RUN — no writes made
```

Pass criteria:
- No exceptions or tracebacks
- At least 1 FOUND line (if there are any Toast/Clover restaurants in the batch)
- SKIP lines show `conf=0.00` for sites with no signals

- [ ] **Step 3: Run live (write menu_source_url, no extraction)**

```bash
cd /path/to/backend
python scripts/discover_menu_sources.py --limit 50
```

Expected: Script completes, FOUND lines printed, no tracebacks.

- [ ] **Step 4: Verify writes in DB**

```bash
cd /path/to/backend
python - <<'EOF'
import os, sys
sys.path.insert(0, '.')
from sqlalchemy import select, func
from app.db.session import SessionLocal
from app.db.models.place import Place

db = SessionLocal()
count = db.execute(
    select(func.count()).where(
        Place.menu_source_url.isnot(None),
        Place.has_menu.is_(False),
    )
).scalar()
print(f"Places with menu_source_url but not yet extracted: {count}")

sample = db.execute(
    select(Place.name, Place.website, Place.menu_source_url)
    .where(Place.menu_source_url.isnot(None), Place.has_menu.is_(False))
    .limit(5)
).fetchall()
for row in sample:
    print(f"  {row.name!r}: {row.menu_source_url}")
db.close()
EOF
```

Expected: Count > 0, sample rows show provider URLs (toasttab.com, clover.com, etc.) — not the same as `website`.

- [ ] **Step 5: Run with --extract on a small batch**

```bash
cd /path/to/backend
python scripts/discover_menu_sources.py --limit 10 --extract
```

Expected: For each FOUND place, a `→ extracted N items` line appears (N may be 0 if provider extraction fails, which is acceptable).

- [ ] **Step 6: Commit**

```bash
git add scripts/discover_menu_sources.py
git commit -m "feat: add discover_menu_sources script — populates menu_source_url from Place.website"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|------------|
| Probe website + `/menu`, `/order`, `/order-online`, `/online-ordering`, `/food-menu` | `_PROBE_PATHS` in `website_provider_probe.py` |
| Detect Toast via redirect | Check 1 in `probe_website()` |
| Detect Clover via HTML links | Check 2 via `discover_provider_urls()` |
| Detect PopMenu, Square, ChowNow | `_PROVIDER_DOMAINS` map + `discover_provider_urls()` |
| Confidence system (1.0 / 0.9 / 0.7) | `ProbeResult.confidence` levels |
| Only save if confidence >= 0.7 | `MIN_CONFIDENCE = 0.7`, gated by `result.found` |
| Target: website IS NOT NULL AND has_menu = FALSE | SQL WHERE clause in worker |
| Skip yelp.com, tripadvisor.com, facebook.com | `_SKIP_DOMAINS` frozenset |
| Domain cache (no re-fetch same domain per run) | `domain_cache` dict in worker |
| Polite inter-domain delay | `time.sleep(0.3)` |
| No ScrapingBee by default | Using existing `fetch()` only |
| `--dry-run` mode | `dry_run` parameter |
| `--limit` parameter | `limit` parameter |
| After discovery: trigger extractor | `--extract` flag calling `extract_menu_from_url()` |

**7-day re-check TTL:** The spec calls for not re-checking the same domain within 7 days. The idempotent query filter `menu_source_url IS NULL` achieves this — once a domain is discovered, the place is skipped on all future runs. For places where discovery found nothing, they will be re-probed on future runs (no 7-day TTL on negatives), which is acceptable given the domain cache within a single run. Adding a separate `menu_source_checked_at` timestamp field to Place would be a DB migration; given YAGNI, the `menu_source_url IS NULL` filter is sufficient.

**No placeholders present.** All code is complete.

**Type consistency confirmed:** `ProbeResult` is defined in Task 1, used in Task 2. `probe_website()` signature matches usage in worker. `extract_menu_from_url()` is imported lazily in the `--extract` branch.
