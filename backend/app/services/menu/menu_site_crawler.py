from __future__ import annotations

import logging
from typing import List, Optional, Set
from urllib.parse import urljoin, urlparse

from app.services.network.http_fetcher import fetch
from app.services.menu.menu_link_discovery import discover_menu_links
from app.services.menu.menu_extraction_router import extract_menu
from app.services.menu.extraction.extraction_result_ranker import rank_extraction_results
from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


MAX_CRAWL_PAGES = 8
MAX_TOTAL_ITEMS = 1500
EARLY_EXIT_THRESHOLD = 20  # 🔥 if we already got enough items, stop


# -----------------------------------------------------
# HELPERS
# -----------------------------------------------------

def _normalize_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        scheme = parsed.scheme or "https"
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        return f"{scheme}://{netloc}{path}"
    except Exception:
        return url


def _same_domain(a: str, b: str) -> bool:
    try:
        return urlparse(a).netloc == urlparse(b).netloc
    except Exception:
        return False


def _fetch_page(url: str) -> Optional[str]:
    try:
        response = fetch(url, mode="document", referer=url)

        if not response or response.status_code != 200:
            return None

        html = response.text

        if not html or len(html) < 50:
            return None

        return html

    except Exception as exc:
        logger.debug("menu_page_fetch_failed url=%s error=%s", url, exc)
        return None


def _dedupe_items(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:
    seen = set()
    out = []

    for item in items:
        key = (
            f"{(item.name or '').strip().lower()}|"
            f"{(item.section or '').strip().lower()}|"
            f"{str(item.price or '').strip()}"
        )

        if key in seen:
            continue

        seen.add(key)
        out.append(item)

        if len(out) >= MAX_TOTAL_ITEMS:
            break

    return out


def _extract_from_page(url: str, html: str) -> List[ExtractedMenuItem]:
    try:
        items = extract_menu(html=html, url=url)
        return _dedupe_items(items or [])
    except Exception as exc:
        logger.debug("menu_extraction_failed url=%s error=%s", url, exc)
        return []


# -----------------------------------------------------
# MAIN
# -----------------------------------------------------

def crawl_menu(base_url: str) -> List[ExtractedMenuItem]:

    base_url = _normalize_url(base_url)

    visited: Set[str] = set()
    results = []

    homepage_html = _fetch_page(base_url)

    if not homepage_html:
        return []

    visited.add(base_url)

    # -----------------------------------------------------
    # HOMEPAGE
    # -----------------------------------------------------

    homepage_items = _extract_from_page(base_url, homepage_html)

    if homepage_items:
        results.append({
            "extractor": "homepage",
            "url": base_url,
            "items": homepage_items,
        })

        # 🔥 EARLY EXIT
        if len(homepage_items) >= EARLY_EXIT_THRESHOLD:
            logger.info(
                "menu_crawl_early_exit_homepage url=%s items=%s",
                base_url,
                len(homepage_items),
            )
            return homepage_items[:MAX_TOTAL_ITEMS]

    # -----------------------------------------------------
    # DISCOVERY (already ranked upstream)
    # -----------------------------------------------------

    discovered_links = discover_menu_links(homepage_html, base_url)

    crawled = 0

    for link in discovered_links:

        if crawled >= MAX_CRAWL_PAGES:
            break

        try:
            link = urljoin(base_url, link)
        except Exception:
            continue

        link = _normalize_url(link)

        # 🔥 DOMAIN LOCK
        if not _same_domain(link, base_url):
            continue

        if link in visited:
            continue

        visited.add(link)

        html = _fetch_page(link)

        if not html:
            continue

        items = _extract_from_page(link, html)

        if items:
            results.append({
                "extractor": "menu_page",
                "url": link,
                "items": items,
            })

            # 🔥 EARLY EXIT IF GOOD RESULT
            if len(items) >= EARLY_EXIT_THRESHOLD:
                logger.info(
                    "menu_crawl_early_exit_page url=%s items=%s",
                    link,
                    len(items),
                )
                return items[:MAX_TOTAL_ITEMS]

        crawled += 1

    # -----------------------------------------------------
    # RANKING
    # -----------------------------------------------------

    ranked = rank_extraction_results(results)

    if ranked:
        items = _dedupe_items(ranked.get("items", []))

        logger.info(
            "menu_crawl_success url=%s pages=%s items=%s",
            base_url,
            len(visited),
            len(items),
        )

        return items[:MAX_TOTAL_ITEMS]

    logger.debug(
        "menu_crawl_no_results url=%s pages=%s",
        base_url,
        len(visited),
    )

    return []