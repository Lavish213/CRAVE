from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from app.pipeline.snapshot_writer import MenuSnapshotWriter
from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.api_endpoint_discovery import discover_api_endpoints
from app.services.menu.extraction.api_menu_extractor import extract_api_menu
from app.services.menu.extraction.extraction_result_ranker import rank_extraction_results
from app.services.menu.extraction.graphql_menu_extractor import extract_graphql_menu
from app.services.menu.extraction.hydration_menu_extractor import extract_hydration_menu
from app.services.menu.extraction.html_menu_extractor import extract_html_menu
from app.services.menu.extraction.iframe_menu_detector import detect_menu_iframes
from app.services.menu.extraction.jsonld_menu_extractor import extract_jsonld_menu
from app.services.menu.extraction.pdf_menu_extractor import extract_pdf_menu
from app.services.menu.extraction.provider_detector import detect_provider
from app.services.menu.extraction.js.js_extractor import extract_menu_from_js
from app.services.menu.providers.provider_registry import extract_with_fallback
from app.services.network.browser_escalation import fetch_with_browser, should_browser_escalate
from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)


MAX_ITEMS = 1500
MAX_API_ENDPOINTS = 20
MAX_IFRAMES = 10

PROVIDER_FAST_RETURN_MIN = 5
API_FAST_RETURN_MIN = 10
HTML_FAST_RETURN_MIN = 12
MIN_GOOD_RESULT = 5


def _safe_text(val: Any) -> str:
    try:
        return str(val).strip()
    except Exception:
        return ""


def _safe_extract(fn, *args) -> List[ExtractedMenuItem]:
    if not fn:
        return []

    try:
        result = fn(*args) or []
        if not isinstance(result, list):
            return []
        return result
    except Exception as exc:
        logger.debug(
            "extract_fail fn=%s error=%s",
            getattr(fn, "__name__", repr(fn)),
            exc,
        )
        return []


def _safe_provider_extract(
    provider: Optional[str],
    html: str,
    url: Optional[str],
) -> List[ExtractedMenuItem]:
    if not provider or not url:
        return []

    try:
        items = extract_with_fallback(provider, url, html)
        if not isinstance(items, list):
            return []
        return items[:MAX_ITEMS]
    except Exception as exc:
        logger.debug(
            "provider_extract_failed provider=%s url=%s error=%s",
            provider,
            url,
            exc,
        )
        return []


def _safe_api_extract(html: str, url: Optional[str]) -> List[ExtractedMenuItem]:
    items: List[ExtractedMenuItem] = []

    if not html or not url:
        return items

    try:
        endpoints = discover_api_endpoints(html, url)[:MAX_API_ENDPOINTS]

        for endpoint in endpoints:
            try:
                endpoint_text = _safe_text(endpoint).lower()

                if not endpoint_text:
                    continue

                if any(
                    blocked in endpoint_text
                    for blocked in (
                        "login",
                        "admin",
                        "validate",
                        "customer",
                        "account",
                        "auth",
                        "session",
                        "app.link",
                        "download",
                        "signin",
                    )
                ):
                    continue

                if "graphql" in endpoint_text:
                    result = extract_graphql_menu(endpoint, url)
                else:
                    result = extract_api_menu(endpoint, url)

                if result:
                    items.extend(result)

                if len(items) >= MAX_ITEMS:
                    break

            except Exception as exc:
                logger.debug(
                    "api_endpoint_extract_failed endpoint=%s url=%s error=%s",
                    endpoint,
                    url,
                    exc,
                )
                continue

    except Exception as exc:
        logger.debug("api_discovery_failed url=%s error=%s", url, exc)

    return items[:MAX_ITEMS]


def _safe_iframe_extract(html: str, url: Optional[str]) -> List[ExtractedMenuItem]:
    items: List[ExtractedMenuItem] = []

    if not html or not url:
        return items

    try:
        iframe_urls = detect_menu_iframes(html, url)[:MAX_IFRAMES]

        for iframe_url in iframe_urls:
            try:
                response = fetch(iframe_url, mode="document", referer=url)

                if not response or getattr(response, "status_code", None) != 200:
                    continue

                iframe_html = response.text or ""
                if not iframe_html:
                    continue

                extracted = extract_html_menu(iframe_html, iframe_url)
                if extracted:
                    items.extend(extracted)

                if len(items) >= MAX_ITEMS:
                    break

            except Exception as exc:
                logger.debug(
                    "iframe_extract_failed iframe_url=%s parent_url=%s error=%s",
                    iframe_url,
                    url,
                    exc,
                )
                continue

    except Exception as exc:
        logger.debug("iframe_discovery_failed url=%s error=%s", url, exc)

    return items[:MAX_ITEMS]


def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:
    seen = set()
    out: List[ExtractedMenuItem] = []

    for item in items:
        name = _safe_text(getattr(item, "name", None)).lower()
        if not name:
            continue

        key = (
            f"{name}|"
            f"{getattr(item, 'price', None)}|"
            f"{_safe_text(getattr(item, 'section', None)).lower()}|"
            f"{_safe_text(getattr(item, 'description', None)).lower()}"
        )

        if key in seen:
            continue

        seen.add(key)
        out.append(item)

        if len(out) >= MAX_ITEMS:
            break

    return out


def _normalize_snapshot_items(items: List[ExtractedMenuItem]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []

    for item in items:
        try:
            normalized.append(
                {
                    "name": _safe_text(getattr(item, "name", None)),
                    "category": _safe_text(getattr(item, "section", None)) or None,
                    "price": getattr(item, "price", None),
                    "description": _safe_text(getattr(item, "description", None)) or None,
                    "image": getattr(item, "image", None),
                }
            )
        except Exception:
            continue

    return [row for row in normalized if row.get("name")]


def _write_snapshot(
    place_id: Optional[str],
    url: Optional[str],
    method: str,
    items: List[ExtractedMenuItem],
) -> None:
    if not place_id:
        return

    try:
        MenuSnapshotWriter().write(
            place_id=place_id,
            extraction_method=method,
            source_url=url,
            success=bool(items),
            normalized_items=_normalize_snapshot_items(items),
        )
    except Exception as exc:
        logger.debug(
            "snapshot_fail place_id=%s method=%s url=%s error=%s",
            place_id,
            method,
            url,
            exc,
        )


def _return(
    place_id: Optional[str],
    url: Optional[str],
    method: str,
    items: List[ExtractedMenuItem],
) -> List[ExtractedMenuItem]:
    final_items = _dedupe(items)[:MAX_ITEMS]

    logger.info(
        "menu_extract_final method=%s count=%s url=%s",
        method,
        len(final_items),
        url,
    )

    _write_snapshot(place_id, url, method, final_items)

    return final_items


def _detect_provider(html: str, url: Optional[str]) -> Optional[str]:
    provider: Optional[str] = None

    try:
        provider = detect_provider(html or "", url)
    except Exception as exc:
        logger.debug("provider_detect_failed url=%s error=%s", url, exc)

    if provider or not url:
        return provider

    lowered_url = url.lower()

    if "toasttab" in lowered_url:
        return "toast"
    if "clover" in lowered_url:
        return "clover"
    if "popmenu" in lowered_url:
        return "popmenu"
    if "chownow" in lowered_url:
        return "chownow"
    if "squareup" in lowered_url or "square.site" in lowered_url or "order.online" in lowered_url:
        return "square"

    return None


def _run_extraction_pass(
    *,
    html: str,
    url: Optional[str],
    place_id: Optional[str],
    provider: Optional[str],
    allow_browser_escalation: bool,
) -> List[ExtractedMenuItem]:
    provider_items = _safe_provider_extract(provider, html, url)
    if len(provider_items) >= PROVIDER_FAST_RETURN_MIN:
        return _return(place_id, url, "provider_fast", provider_items)

    if not html:
        return _return(place_id, url, "provider_only", provider_items)

    hydration_items = _safe_extract(extract_hydration_menu, html, url)
    if len(hydration_items) >= PROVIDER_FAST_RETURN_MIN:
        return _return(place_id, url, "hydration_fast", hydration_items)

    jsonld_items = _safe_extract(extract_jsonld_menu, html, url)
    js_items = _safe_extract(extract_menu_from_js, html, url)

    api_items = _safe_api_extract(html, url)
    if len(api_items) >= API_FAST_RETURN_MIN:
        return _return(place_id, url, "api", api_items)

    html_items = _safe_extract(extract_html_menu, html, url)
    if len(html_items) >= HTML_FAST_RETURN_MIN:
        return _return(place_id, url, "html", html_items)

    iframe_items = _safe_iframe_extract(html, url)

    results = [
        {"extractor": "provider", "items": _dedupe(provider_items)},
        {"extractor": "hydration", "items": _dedupe(hydration_items)},
        {"extractor": "jsonld", "items": _dedupe(jsonld_items)},
        {"extractor": "js", "items": _dedupe(js_items)},
        {"extractor": "api", "items": _dedupe(api_items)},
        {"extractor": "html", "items": _dedupe(html_items)},
        {"extractor": "iframe", "items": _dedupe(iframe_items)},
    ]

    best: List[ExtractedMenuItem] = []
    best_method = "fallback"

    try:
        ranked = rank_extraction_results(results)
        if ranked:
            best = ranked.get("items", []) or []
            best_method = ranked.get("extractor") or "ranked"
    except Exception as exc:
        logger.debug("rank_failed url=%s error=%s", url, exc)

    if len(best) >= MIN_GOOD_RESULT:
        return _return(place_id, url, best_method, best)

    fallback = max(
        [
            _dedupe(provider_items),
            _dedupe(hydration_items),
            _dedupe(api_items),
            _dedupe(js_items),
            _dedupe(html_items),
            _dedupe(jsonld_items),
            _dedupe(iframe_items),
        ],
        key=len,
        default=[],
    )

    final = _return(place_id, url, "fallback", fallback)

    if final or not allow_browser_escalation or not url:
        return final

    if should_browser_escalate(reason="empty_html", attempt=2):
        browser_html = fetch_with_browser(url, referer=url)

        if browser_html and browser_html != html:
            logger.info("menu_browser_escalation_success url=%s", url)
            return _run_extraction_pass(
                html=browser_html,
                url=url,
                place_id=place_id,
                provider=provider,
                allow_browser_escalation=False,
            )

    return final


def extract_menu(
    html: str,
    url: Optional[str] = None,
    place_id: Optional[str] = None,
) -> List[ExtractedMenuItem]:
    if not html and not url:
        return []

    if url and url.lower().endswith(".pdf"):
        return _return(place_id, url, "pdf", _safe_extract(extract_pdf_menu, url))

    provider = _detect_provider(html, url)

    if not html:
        provider_items = _safe_provider_extract(provider, html, url)
        if provider_items:
            return _return(place_id, url, "provider_only", provider_items)

        if url and should_browser_escalate(reason="empty_html", attempt=2):
            browser_html = fetch_with_browser(url, referer=url)
            if browser_html:
                return _run_extraction_pass(
                    html=browser_html,
                    url=url,
                    place_id=place_id,
                    provider=provider,
                    allow_browser_escalation=False,
                )

        return []

    return _run_extraction_pass(
        html=html,
        url=url,
        place_id=place_id,
        provider=provider,
        allow_browser_escalation=True,
    )