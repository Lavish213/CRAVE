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

def _parse_price(value: Any) -> Optional[int]:
    """Convert Toast price value to cents (int).

    Toast API returns prices as integers in cents (e.g. 1299 = $12.99)
    or occasionally as floats (e.g. 12.99). Normalize to cents.
    """
    if value is None:
        return None

    try:
        if isinstance(value, int):
            # Already cents if >= 100, else assume dollars
            return value if value >= 100 else int(value * 100)

        if isinstance(value, float):
            # Assume dollars if < 100 (e.g. 12.99), else cents
            if value < 100:
                return round(value * 100)
            return int(value)

        # String — strip currency symbols, convert
        s = str(value).strip().lstrip("$").replace(",", "")
        f = float(s)
        return round(f * 100) if f < 100 else int(f)

    except Exception:
        return None


# ---------------------------------------------------------
# DEDUPE
# ---------------------------------------------------------

def _dedupe(items: List[ExtractedMenuItem]) -> List[ExtractedMenuItem]:
    seen = set()
    out: List[ExtractedMenuItem] = []

    for item in items:
        # price_cents is int|None — cannot call .strip() on int.
        # Use empty string for None, str() for any integer value (including 0).
        _price_key = "" if item.price_cents is None else str(item.price_cents)
        key = (
            f"{(item.name or '').strip().lower()}|"
            f"{_price_key}|"
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

_URL_GUID_PATTERN = re.compile(
    r"/r-([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})",
    re.IGNORECASE,
)


def _extract_guid_from_url(url: Optional[str]) -> Optional[str]:
    """Extract GUID from URL path — e.g. /local/slug/r-{uuid}."""
    if not url:
        return None
    match = _URL_GUID_PATTERN.search(url)
    return match.group(1) if match else None


def _extract_guid(html: Optional[str]) -> Optional[str]:
    if not html:
        return None

    match = TOAST_GUID_PATTERN.search(html)
    return match.group(1) if match else None


def _extract_slug(url: Optional[str]) -> Optional[str]:
    """
    Extract the usable restaurant slug from Toast URL variants:
      /local/<slug>                    → slug
      /local/<slug>/r-<guid>           → slug (not the trailing GUID)
      /online/<slug>                   → slug
      toasttab.com/<slug>              → slug
    """
    if not url:
        return None

    try:
        import re as _re
        clean = url.split("?")[0].split("#")[0].rstrip("/")
        parts = [
            p for p in clean.split("/")
            if p and "." not in p and "http" not in p.lower()
        ]

        if not parts:
            return None

        # Remove trailing "order-online" segment
        if parts[-1] == "order-online":
            parts = parts[:-1]

        if not parts:
            return None

        # /local/<slug>  or  /local/<slug>/r-<guid>
        if "local" in parts:
            idx = parts.index("local")
            if idx + 1 < len(parts):
                return parts[idx + 1]  # slug, not the trailing GUID

        # /online/<slug>
        if "online" in parts:
            idx = parts.index("online")
            if idx + 1 < len(parts):
                return parts[idx + 1]

        # Direct: toasttab.com/<slug>  — single meaningful segment
        last = parts[-1]
        # Skip raw GUIDs: r-xxxxxxxx-... or full UUID
        if _re.match(r"r-[a-f0-9]{8}-", last) or _re.fullmatch(
            r"[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", last
        ):
            if len(parts) >= 2:
                return parts[-2]
            return None

        return last

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

    guid = _extract_guid(html) or _extract_guid_from_url(url)
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

            # Toast API items may carry an imageUrl (item-level food photo)
            image_url = (
                item.get("imageUrl")
                or item.get("image_url")
                or item.get("image")
                or None
            )
            if image_url and not isinstance(image_url, str):
                image_url = None

            items.append(
                ExtractedMenuItem(
                    name=str(name),
                    price_cents=_parse_price(item.get("price")),
                    section=section_name,
                    currency="USD",
                    description=item.get("description"),
                    image_url=image_url,
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