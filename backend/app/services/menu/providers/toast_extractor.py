from __future__ import annotations

import logging
import re
from typing import List, Optional, Dict, Any

from app.services.network.http_fetcher import fetch
from app.services.menu.contracts import ExtractedMenuItem


logger = logging.getLogger(__name__)

MAX_ITEMS = 1500
MAX_RECURSION_DEPTH = 20


TOAST_GUID_PATTERN = re.compile(
    r"[\"']restaurantGuid[\"']\s*[:=]\s*[\"']([a-f0-9\-]+)[\"']",
    re.IGNORECASE,
)


# ---------------------------------------------------------
# PRICE
# ---------------------------------------------------------

def _parse_price(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:
        if isinstance(value, (int, float)):
            if value > 100:
                value = value / 100
            return f"{value:.2f}"

        return str(value)
    except Exception:
        return None


# ---------------------------------------------------------
# DEDUPE
# ---------------------------------------------------------

def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:
    seen = set()
    out: List[ExtractedMenuItem] = []

    for item in items:
        key = (
            f"{(item.name or '').strip().lower()}|"
            f"{(item.price or '').strip()}|"
            f"{(item.section or '').strip().lower()}"
        )

        if key in seen:
            continue

        seen.add(key)
        out.append(item)

        if len(out) >= MAX_ITEMS:
            break

    return out


# ---------------------------------------------------------
# VALIDATION
# ---------------------------------------------------------

def _is_probably_toast(url: Optional[str], html: Optional[str]) -> bool:
    if url and "toasttab.com" in url.lower():
        return True

    # Only match toasttab.com domain in HTML — not "toast" text (French toast FP)
    if html and "toasttab.com" in html.lower():
        return True

    return False


# ---------------------------------------------------------
# GUID / SLUG (FIXED 🔥)
# ---------------------------------------------------------

def _extract_guid(html: Optional[str]) -> Optional[str]:
    if not html:
        return None

    match = TOAST_GUID_PATTERN.search(html)
    return match.group(1) if match else None


def _extract_slug(url: Optional[str]) -> Optional[str]:
    if not url:
        return None

    try:
        parts = url.split("/")
        parts = [p for p in parts if p and "http" not in p]

        if not parts:
            return None

        if parts[-1] == "order-online":
            parts = parts[:-1]

        if not parts:
            return None

        return parts[-1]

    except Exception:
        return None


# ---------------------------------------------------------
# API CANDIDATES (FULL FIX 🔥)
# ---------------------------------------------------------

def _build_api_candidates(
    url: Optional[str],
    html: Optional[str],
) -> List[str]:

    candidates: List[str] = []

    guid = _extract_guid(html)
    slug = _extract_slug(url)

    # GUID (best)
    if guid:
        candidates.extend([
            f"https://toasttab.com/api/menus/v2/restaurant/{guid}",
            f"https://toasttab.com/api/menus/v3/restaurant/{guid}",
            f"https://order.toasttab.com/api/menus/v2/restaurant/{guid}",
            f"https://order.toasttab.com/api/menus/v3/restaurant/{guid}",
        ])

    # SLUG — use actual Toast public URL pattern (/{slug}/v3/menu)
    if slug:
        candidates.extend([
            f"https://www.toasttab.com/{slug}/v3/menu",
            f"https://toasttab.com/{slug}/v3/menu",
            f"https://order.toasttab.com/{slug}/v3/menu",
        ])

    return list(dict.fromkeys(candidates))


# ---------------------------------------------------------
# FETCH
# ---------------------------------------------------------

def _fetch_toast_api(url: str) -> Optional[Dict[str, Any]]:
    try:
        res = fetch(
            url,
            mode="api",
            headers={
                "Accept": "application/json, text/plain, */*",
                "Referer": "https://www.toasttab.com/",
                "Origin": "https://www.toasttab.com",
            },
        )

        if res.status_code != 200:
            logger.debug("toast_api_status_fail url=%s status=%s", url, res.status_code)
            return None

        try:
            return res.json()
        except Exception:
            logger.debug("toast_json_invalid url=%s", url)
            return None

    except Exception as exc:
        logger.debug("toast_api_fail url=%s err=%s", url, exc)
        return None


# ---------------------------------------------------------
# PARSE
# ---------------------------------------------------------

def _parse_groups(groups, section, depth: int = 0):

    if depth > MAX_RECURSION_DEPTH:
        return []

    items: List[ExtractedMenuItem] = []

    for group in groups:

        section_name = group.get("name") or section

        for item in group.get("items", []):

            name = item.get("name")
            if not name:
                continue

            items.append(
                ExtractedMenuItem(
                    name=str(name),
                    price=_parse_price(item.get("price")),
                    section=section_name,
                    currency="USD",
                    description=item.get("description"),
                    provider="toast",
                    source_type="provider",
                )
            )

        if group.get("groups"):
            items.extend(_parse_groups(group["groups"], section_name, depth + 1))

    return items


def _parse_menu(data):

    items: List[ExtractedMenuItem] = []

    if data.get("groups"):
        items.extend(_parse_groups(data["groups"], None))

    for menu in data.get("menus", []):
        if menu.get("groups"):
            items.extend(_parse_groups(menu["groups"], None))

    return items


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

def extract_toast_menu(
    html: Optional[str] = None,
    url: Optional[str] = None,
) -> List[ExtractedMenuItem]:

    if not _is_probably_toast(url, html):
        return []

    candidates = _build_api_candidates(url, html)

    if not candidates:
        logger.debug("toast_no_candidates url=%s", url)
        return []

    for api_url in candidates:

        data = _fetch_toast_api(api_url)

        if not data:
            continue

        try:
            items = _parse_menu(data)
            items = _dedupe(items)

            if items:
                logger.info(
                    "toast_success api=%s items=%s",
                    api_url,
                    len(items),
                )
                return items[:MAX_ITEMS]

        except Exception as exc:
            logger.debug("toast_parse_fail api=%s err=%s", api_url, exc)

    logger.debug("toast_all_candidates_failed url=%s", url)
    return []