from __future__ import annotations

import logging
import time
from typing import Optional, List, Dict, Any

from sqlalchemy.orm import Session

from app.services.menu.contracts import ExtractedMenu, ExtractedMenuItem
from app.services.menu.extraction.fetch_html import fetch_html
from app.services.menu.extraction.provider_detector import detect_provider
from app.services.menu.extraction.provider_menu_fetcher import fetch_provider_menu
from app.services.menu.extraction.jsonld_menu_extractor import extract_jsonld_menu
from app.services.menu.extraction.hydration_menu_extractor import extract_hydration_menu
from app.services.menu.extraction.html_menu_extractor import extract_menu_from_html
from app.services.menu.extraction.pdf_menu_extractor import extract_pdf_menu
from app.services.menu.extraction.extraction_result_ranker import rank_extraction_results
from app.services.menu.extraction.js.js_extraction_service import extract_menu_from_js
from app.services.menu.extraction.browser_fallback import extract_with_browser
from app.services.menu.orchestration.ingest_menu_items import ingest_menu_items
from app.services.menu.providers.provider_normalizer import normalize_items

from app.services.menu.providers.toast_direct_extractor import extract_toast_direct
from app.services.menu.providers.clover_direct_extractor import extract_clover_direct
from app.services.menu.providers.popmenu_direct_extractor import extract_popmenu_direct


logger = logging.getLogger(__name__)

MAX_MENU_ITEMS = 1000
MAX_EXTRACTOR_RESULTS = 10


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _build_result(extractor: str, items) -> Dict[str, Any]:
    if not items:
        return {}

    try:
        normalized = normalize_items(items)
    except Exception as exc:
        logger.debug("normalize_failed extractor=%s error=%s", extractor, exc)
        return {}

    if not normalized:
        return {}

    return {
        "extractor": extractor,
        "items": normalized,
    }


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def extract_menu_from_url(
    *,
    db: Session,
    place_id: str,
    url: str,
) -> ExtractedMenu:

    if not db or not place_id or not url:
        logger.warning("menu_invalid_input")
        return ExtractedMenu(items=[], source_url=url)

    start_time = time.time()
    results: List[Dict[str, Any]] = []
    html = ""

    # ---------------------------------------------------------
    # FETCH HTML
    # ---------------------------------------------------------

    try:
        html = fetch_html(url)
    except Exception as exc:
        logger.warning("menu_fetch_failed place=%s url=%s error=%s", place_id, url, exc)

    # ---------------------------------------------------------
    # PROVIDER DETECT
    # ---------------------------------------------------------

    provider: Optional[str] = None

    try:
        provider = detect_provider(html, url)
    except Exception:
        provider = None

    if provider:
        logger.info("provider_detected place=%s provider=%s", place_id, provider)

    # ---------------------------------------------------------
    # DIRECT PROVIDERS
    # ---------------------------------------------------------

    try:
        if provider == "toast":
            results.append(_build_result("toast_direct", extract_toast_direct(url)))

        elif provider == "clover":
            results.append(_build_result("clover_direct", extract_clover_direct(url)))

        elif provider == "popmenu":
            results.append(_build_result("popmenu_direct", extract_popmenu_direct(url)))

    except Exception as exc:
        logger.debug("direct_provider_failed provider=%s error=%s", provider, exc)

    # ---------------------------------------------------------
    # PROVIDER SCRAPER
    # ---------------------------------------------------------

    try:
        provider_menu = fetch_provider_menu(url=url, html=html)
        if provider_menu and provider_menu.items:
            results.append(_build_result("provider", provider_menu.items))
    except Exception as exc:
        logger.debug("provider_scraper_failed error=%s", exc)

    # ---------------------------------------------------------
    # JSONLD
    # ---------------------------------------------------------

    if html:
        try:
            results.append(_build_result("jsonld", extract_jsonld_menu(html)))
        except Exception:
            pass

    # ---------------------------------------------------------
    # HYDRATION
    # ---------------------------------------------------------

    if html:
        try:
            results.append(_build_result("hydration", extract_hydration_menu(html)))
        except Exception:
            pass

    # ---------------------------------------------------------
    # HTML
    # ---------------------------------------------------------

    if html:
        try:
            html_menu = extract_menu_from_html(html=html, source_url=url)
            if html_menu and html_menu.items:
                results.append(_build_result("html", html_menu.items))
        except Exception:
            pass

    # ---------------------------------------------------------
    # JS
    # ---------------------------------------------------------

    try:
        results.append(_build_result("js", extract_menu_from_js(html, url)))
    except Exception:
        pass

    # ---------------------------------------------------------
    # PDF
    # ---------------------------------------------------------

    if url.lower().endswith(".pdf"):
        try:
            results.append(_build_result("pdf", extract_pdf_menu(url)))
        except Exception:
            pass

    # ---------------------------------------------------------
    # BROWSER (ALWAYS LAST)
    # ---------------------------------------------------------

    try:
        results.append(_build_result("browser", extract_with_browser(url)))
    except Exception:
        pass

    # ---------------------------------------------------------
    # CLEAN RESULTS
    # ---------------------------------------------------------

    results = [r for r in results if r and r.get("items")]

    if not results:
        logger.warning("menu_no_results place=%s url=%s", place_id, url)
        return ExtractedMenu(items=[], source_url=url)

    results = results[:MAX_EXTRACTOR_RESULTS]

    # ---------------------------------------------------------
    # RANK
    # ---------------------------------------------------------

    try:
        best = rank_extraction_results(results)
    except Exception as exc:
        logger.error("ranking_failed %s", exc)
        return ExtractedMenu(items=[], source_url=url)

    if not best:
        return ExtractedMenu(items=[], source_url=url)

    items: List[ExtractedMenuItem] = best.get("items") or []

    if not items:
        logger.warning("menu_empty_after_rank place=%s", place_id)
        return ExtractedMenu(items=[], source_url=url)

    items = items[:MAX_MENU_ITEMS]

    # ---------------------------------------------------------
    # INGEST (NON-BLOCKING)
    # ---------------------------------------------------------

    try:
        inserted = ingest_menu_items(
            db=db,
            place_id=place_id,
            extracted_items=items,
            source_url=url,
        )

        logger.info("menu_ingested place=%s count=%s", place_id, inserted)

    except Exception as exc:
        logger.exception("menu_ingest_failed place=%s error=%s", place_id, exc)

    # ---------------------------------------------------------
    # FINAL
    # ---------------------------------------------------------

    logger.info(
        "menu_complete place=%s extractor=%s items=%s time=%ss",
        place_id,
        best.get("extractor"),
        len(items),
        round(time.time() - start_time, 3),
    )

    return ExtractedMenu(
        items=items,
        source_url=url,
    )