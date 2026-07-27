from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from app.services.network.http_fetcher import fetch
from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)


MAX_ITEMS = 1200
MAX_PAGES = 10
PER_PAGE = 200

_API_BASE = "https://cdn5.editmysite.com/app/store/api/v28/editor/users"

# ---------------------------------------------------------
# Bootstrap state extraction
# ---------------------------------------------------------

_BOOTSTRAP_RE = re.compile(r'window\.__BOOTSTRAP_STATE__\s*=\s*\{')


def _parse_bootstrap_state(html: str) -> Optional[Dict[str, Any]]:
    """Extract window.__BOOTSTRAP_STATE__ JSON blob from raw HTML."""
    m = _BOOTSTRAP_RE.search(html)
    if not m:
        return None

    # The match ends at the opening `{` — start raw_decode there
    json_start = m.end() - 1  # back up to include `{`
    try:
        obj, _ = json.JSONDecoder().raw_decode(html[json_start:])
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _extract_ids(state: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    """Return (user_id, site_id) from __BOOTSTRAP_STATE__."""
    try:
        user_id = str(state["siteData"]["user"]["id"])
    except (KeyError, TypeError):
        user_id = None

    try:
        props = state["siteData"]["site"]["properties"]
        site_id = str(
            props.get("classicSiteID")
            or props.get("catalogSiteId")
            or ""
        ).strip() or None
    except (KeyError, TypeError):
        site_id = None

    return user_id, site_id


# ---------------------------------------------------------
# API calls
# ---------------------------------------------------------

def _fetch_json(api_url: str, referer: str) -> Optional[Any]:
    try:
        res = fetch(
            api_url,
            mode="api",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": referer,
                "Origin": "https://www.squareuponline.com",
            },
        )
        if res.status_code != 200:
            logger.debug("square_api_status url=%s status=%s", api_url, res.status_code)
            return None
        return res.json()
    except Exception as exc:
        logger.debug("square_api_error url=%s err=%s", api_url, exc)
        return None


def _fetch_categories(user_id: str, site_id: str, referer: str) -> Dict[str, str]:
    """Return {category_id: category_name}."""
    url = (
        f"{_API_BASE}/{user_id}/sites/{site_id}/categories"
        "?per_page=100&lang=en&show_hidden=0"
    )
    data = _fetch_json(url, referer)
    if not data:
        return {}

    result: Dict[str, str] = {}
    for cat in (data.get("data") or []):
        cid = cat.get("id") or cat.get("site_category_id")
        name = cat.get("name")
        if cid and name:
            result[str(cid)] = str(name)
    return result


def _fetch_all_products(
    user_id: str,
    site_id: str,
    referer: str,
) -> List[Dict]:
    products: List[Dict] = []

    for page in range(1, MAX_PAGES + 1):
        url = (
            f"{_API_BASE}/{user_id}/sites/{site_id}/products"
            f"?page={page}&per_page={PER_PAGE}&lang=en&show_hidden=0"
        )
        data = _fetch_json(url, referer)
        if not data:
            break

        page_items = data.get("data") or []
        products.extend(page_items)

        pagination = (data.get("meta") or {}).get("pagination") or {}
        total_pages = pagination.get("total_pages") or 1
        if page >= total_pages or len(products) >= MAX_ITEMS:
            break

    return products


# ---------------------------------------------------------
# Parse
# ---------------------------------------------------------

def _parse_products(
    products: List[Dict],
    cat_map: Dict[str, str],
) -> List[ExtractedMenuItem]:
    items: List[ExtractedMenuItem] = []

    for p in products:
        name = (p.get("name") or "").strip()
        if not name:
            continue

        # Price: API returns subunits (cents) as integer
        price_obj = p.get("price") or {}
        raw_price = price_obj.get("low_subunits")
        price_cents: Optional[int] = int(raw_price) if raw_price is not None else None

        # Category: first matching ID in cat_map
        section: Optional[str] = None
        for cid in (p.get("categoryIds") or []):
            section = cat_map.get(str(cid))
            if section:
                break

        # Image: thumbnail.data.url
        thumb_data = (p.get("thumbnail") or {}).get("data") or {}
        image_url: Optional[str] = thumb_data.get("url") or None
        if image_url and not isinstance(image_url, str):
            image_url = None

        description = (p.get("short_description") or "").strip() or None

        items.append(
            ExtractedMenuItem(
                name=name,
                price_cents=price_cents,
                section=section,
                currency="USD",
                description=description,
                image_url=image_url,
                provider="square",
                source_type="provider",
            )
        )

    return items


# ---------------------------------------------------------
# Dedupe
# ---------------------------------------------------------

def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:
    seen: set = set()
    out: List[ExtractedMenuItem] = []
    for item in items:
        # price_cents is int|None — represent None as '' so "None" string doesn't leak into key
        _price_key = "" if item.price_cents is None else str(item.price_cents)
        key = (
            f"{(item.name or '').strip().lower()}|"
            f"{_price_key}|"
            f"{(item.section or '').strip().lower()}"
        )
        if key not in seen:
            seen.add(key)
            out.append(item)
            if len(out) >= MAX_ITEMS:
                break
    return out


# ---------------------------------------------------------
# Public entry point
# ---------------------------------------------------------

def extract_square_menu(
    html: Optional[str] = None,
    url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    if not html:
        return []

    state = _parse_bootstrap_state(html)
    if not state:
        logger.debug("square_no_bootstrap url=%s", url)
        return []

    user_id, site_id = _extract_ids(state)
    if not user_id or not site_id:
        logger.debug(
            "square_missing_ids user=%s site=%s url=%s",
            user_id, site_id, url,
        )
        return []

    referer = url or "https://www.square.site/"

    try:
        cat_map = _fetch_categories(user_id, site_id, referer)
        products = _fetch_all_products(user_id, site_id, referer)

        if not products:
            logger.debug(
                "square_no_products url=%s user=%s site=%s",
                url, user_id, site_id,
            )
            return []

        items = _parse_products(products, cat_map)
        items = _dedupe(items)

        if items:
            logger.info("square_success url=%s items=%s", url, len(items))

        return items[:MAX_ITEMS]

    except Exception as exc:
        logger.debug("square_extract_failed url=%s err=%s", url, exc)
        return []
