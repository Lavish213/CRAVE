from __future__ import annotations

import json
import logging
import os
import re
import time as time_mod
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


FetchCallable = Callable[[str], Any]

GRUBHUB_API_BASE = "https://api-gtm.grubhub.com/restaurant_gateway/feed"
GRUBHUB_HOME = "https://www.grubhub.com/"
_IMPERSONATE = "chrome110"

_WARM_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
}

_API_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.grubhub.com",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "If-Modified-Since": "0",
}


# =========================================================
# ENV LOADERS
# =========================================================

def _load_grubhub_cookies() -> Dict[str, str]:
    """
    GRUBHUB_COOKIES — two accepted formats:

    Raw string (preferred — paste from DevTools "Copy as cURL"):
        export GRUBHUB_COOKIES='_px2=abc...; _pxvid=def...; utag_main=...'

    JSON dict (legacy):
        export GRUBHUB_COOKIES='{"_px2": "abc...", "_pxvid": "def..."}'

    Obtain via:
        python backend/scripts/grab_grubhub_cookies.py
    """
    raw = os.environ.get("GRUBHUB_COOKIES", "").strip()
    if not raw:
        return {}

    if raw.startswith("{"):
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                return {str(k): str(v) for k, v in parsed.items() if k and v}
        except Exception as exc:
            logger.warning("grubhub_cookies_json_parse_failed error=%s", exc)

    # Raw "name=value; name2=value2" string
    cookies: Dict[str, str] = {}
    for part in raw.split(";"):
        part = part.strip()
        if "=" in part:
            k, _, v = part.partition("=")
            k = k.strip()
            v = v.strip()
            if k:
                cookies[k] = v
    return cookies


def _load_perimeter_x() -> Optional[str]:
    """
    GRUBHUB_PERIMETER_X — the x-perimeter-x JWT token.

    Obtain via:
        python backend/scripts/grab_grubhub_cookies.py
    Or manually from DevTools → request headers → x-perimeter-x.

        export GRUBHUB_PERIMETER_X='eyJ...'
    """
    return os.environ.get("GRUBHUB_PERIMETER_X", "").strip() or None


def _load_feed_id() -> Optional[str]:
    """
    GRUBHUB_FEED_ID — fallback when feed_id cannot be extracted from page HTML.
        export GRUBHUB_FEED_ID=1717110
    """
    return os.environ.get("GRUBHUB_FEED_ID", "").strip() or None


def _load_restaurant_id() -> Optional[str]:
    """
    GRUBHUB_RESTAURANT_ID — the internal Grubhub restaurant ID (second path
    segment in /feed/{feed_id}/{restaurant_id}). This differs from the URL
    slug ID. Captured by grab_grubhub_cookies.py from the intercepted XHR URL.
        export GRUBHUB_RESTAURANT_ID=20513692235
    """
    return os.environ.get("GRUBHUB_RESTAURANT_ID", "").strip() or None


def _load_brand_uuid() -> Optional[str]:
    """
    GRUBHUB_BRAND_UUID — brandUuid query param in the feed API URL.
    Captured from the intercepted XHR URL by grab_grubhub_cookies.py.
        export GRUBHUB_BRAND_UUID=31b2c3c1-007a-11e9-9398-3b46062668fb
    """
    return os.environ.get("GRUBHUB_BRAND_UUID", "").strip() or None


# =========================================================
# FEED ID EXTRACTION
# =========================================================

_FEED_ID_PATTERNS = [
    r'"feedId"\s*:\s*"(\d+)"',
    r'"feedId"\s*:\s*(\d+)',
    r'/restaurant_gateway/feed/(\d+)/',
    r'"feed_id"\s*:\s*"(\d+)"',
    r'"feed_id"\s*:\s*(\d+)',
    r'feedId[=:]\s*"?(\d+)"?',
    r'feed[_-]?id[=:]\s*"?(\d+)"?',
]


def _extract_feed_id_from_html(html: str) -> Optional[str]:
    """
    Scan authenticated restaurant page HTML/JS for embedded feed_id.
    Grubhub embeds it in the Next.js __NEXT_DATA__ blob or JS config.
    """
    for pattern in _FEED_ID_PATTERNS:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    return None


# =========================================================
# URL CONSTRUCTION
# =========================================================

def _extract_restaurant_id(url: str) -> Optional[str]:
    """
    https://www.grubhub.com/restaurant/some-slug/20513692237
    → "20513692237"
    """
    try:
        parsed = urlparse(url)
        segments = [s for s in parsed.path.split("/") if s]
        if not segments:
            return None
        restaurant_id = segments[-1]
        if not re.fullmatch(r"\d+", restaurant_id):
            return None
        return restaurant_id
    except Exception:
        return None


def _build_api_url(
    restaurant_id: str,
    feed_id: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    brand_uuid: Optional[str] = None,
) -> str:
    """
    Build the Grubhub feed API URL.

    Confirmed format from DevTools:
    /restaurant_gateway/feed/{feed_id}/{restaurant_id}
        ?time={epoch_ms}
        &location=POINT({lng}%20{lat})
        &isFutureOrder=false
        &restaurantStatus=ORDERABLE
        &isNonRestaurantMerchant=false
        &merchantTypes=
        &orderType=STANDARD
        &agent=false
        &weightedItemDataIncluded=true
        &task=CATEGORY
        &rpcVariant=YELP_MENU_ITEM_IMAGE
        &platform=WEB
    """
    import uuid
    ts = int(time_mod.time() * 1000)
    operation_id = str(uuid.uuid4())

    url = (
        f"{GRUBHUB_API_BASE}/{feed_id}/{restaurant_id}"
        f"?time={ts}"
        f"&operationId={operation_id}"
        f"&isFutureOrder=false"
        f"&restaurantStatus=ORDERABLE"
    )

    if brand_uuid:
        url += f"&brandUuid={brand_uuid}"

    if lat is not None and lng is not None:
        url += f"&location=POINT({lng}%20{lat})"

    url += (
        f"&isNonRestaurantMerchant=false"
        f"&merchantTypes="
        f"&orderType=STANDARD"
        f"&agent=false"
        f"&weightedItemDataIncluded=true"
        f"&task=CATEGORY"
        f"&platform=WEB"
    )

    return url


# =========================================================
# DEFAULT FETCHER
# =========================================================

GRUBHUB_RESTAURANT_API = "https://api-gtm.grubhub.com/restaurants"


def _default_fetcher(url: str, place: Any = None) -> Optional[Dict[str, Any]]:
    """
    Full flow:

    1. Load GRUBHUB_COOKIES → fail: COOKIES_INVALID
    2. Load GRUBHUB_PERIMETER_X
    3. Create Session(impersonate="chrome110"), inject cookies
    4. Warm: GET grubhub.com
    5. GET /restaurants/{slug_id} → category list + brand_uuid
       fail: FETCH_BLOCKED
    6. For each category: GET /feed/{slug_id}/{cat_id}?task=CATEGORY
       → collect items
    7. Merge all items into combined payload
       fail: PARSE_EMPTY if 0 items total
    8. Return {"object": {"data": {"content": all_items}}, "status": "SUCCESS"}
    """
    import uuid as uuid_mod
    from curl_cffi import requests as cffi_requests

    # ── 1. Extract slug_id from URL ───────────────────────────────────────────
    slug_id = _extract_restaurant_id(url)
    if not slug_id:
        print("FAILURE: PAYLOAD_INVALID\nERROR: cannot parse slug_id from URL", flush=True)
        return None

    # ── 2. Cookies ────────────────────────────────────────────────────────────
    injected_cookies = _load_grubhub_cookies()
    if not injected_cookies:
        print(
            "FAILURE: COOKIES_INVALID\n"
            "ERROR: GRUBHUB_COOKIES env var missing or unparseable.\n"
            "Run: python backend/scripts/grab_grubhub_cookies.py",
            flush=True,
        )
        logger.warning("grubhub_cookies_missing url=%s", url)
        return None

    # ── 3. Perimeter-X ───────────────────────────────────────────────────────
    perimeter_x = _load_perimeter_x()
    if not perimeter_x:
        print(
            "WARNING: GRUBHUB_PERIMETER_X not set — request may 401.\n"
            "Run: python backend/scripts/grab_grubhub_cookies.py",
            flush=True,
        )
        logger.warning("grubhub_perimeter_x_missing url=%s", url)

    lat: Optional[float] = getattr(place, "lat", None) or getattr(place, "latitude", None)
    lng: Optional[float] = getattr(place, "lng", None) or getattr(place, "longitude", None)

    api_headers = dict(_API_HEADERS)
    api_headers["Referer"] = url
    if perimeter_x:
        api_headers["perimeter-x"] = perimeter_x

    for attempt in range(1, 3):
        try:
            session = cffi_requests.Session(impersonate=_IMPERSONATE)
            session.cookies.update(injected_cookies)

            # ── Warm: homepage ────────────────────────────────────────────────
            session.get(GRUBHUB_HOME, headers=dict(_WARM_HEADERS), timeout=10, allow_redirects=True)

            # ── Step 5: GET /restaurants/{slug_id} ────────────────────────────
            rest_url = f"{GRUBHUB_RESTAURANT_API}/{slug_id}"
            rest_resp = session.get(rest_url, headers=api_headers, timeout=15, allow_redirects=False)

            print(f"[FETCH]\nslug_id={slug_id}\nattempt={attempt}\nrestaurant_status={rest_resp.status_code}", flush=True)

            if rest_resp.status_code == 401:
                print("FAILURE: COOKIES_INVALID\nERROR: 401 — cookies expired.", flush=True)
                return None
            if rest_resp.status_code == 403:
                print("FAILURE: FETCH_BLOCKED\nERROR: 403 — PerimeterX block.", flush=True)
                return None
            if rest_resp.status_code != 200:
                print(f"FAILURE: FETCH_BLOCKED\nERROR: HTTP {rest_resp.status_code} from /restaurants", flush=True)
                continue

            try:
                rest_data = rest_resp.json()
            except Exception as e:
                print(f"FAILURE: PAYLOAD_INVALID\nERROR: JSON parse failed on /restaurants: {e}", flush=True)
                continue

            restaurant = rest_data.get("restaurant", {})
            categories = restaurant.get("menu_category_list", [])
            brand_uuid = restaurant.get("brand_uuid") or _load_brand_uuid()

            print(f"categories_found={len(categories)}", flush=True)

            if not categories:
                print("FAILURE: PARSE_EMPTY\nERROR: no categories in restaurant response", flush=True)
                continue

            # ── Step 6: fetch each category via feed endpoint ─────────────────
            # Always use feed endpoint (not inline items) — inline items from
            # /restaurants have a different key structure than feed items and
            # the parser/adapter expects feed format consistently.
            all_items: list = []
            for cat in categories:
                cat_id = cat.get("menu_category_id")
                cat_name = cat.get("name", "?")
                if not cat_id:
                    continue

                feed_url = _build_api_url(
                    restaurant_id=str(cat_id),
                    feed_id=slug_id,
                    lat=lat,
                    lng=lng,
                    brand_uuid=brand_uuid,
                )
                try:
                    feed_resp = session.get(feed_url, headers=api_headers, timeout=15, allow_redirects=False)
                    if feed_resp.status_code != 200:
                        logger.warning("grubhub_cat_fetch_failed cat=%s status=%s", cat_name, feed_resp.status_code)
                        continue
                    feed_data = feed_resp.json()
                    items = (
                        feed_data.get("object", {})
                        .get("data", {})
                        .get("content", [])
                    )
                    if items:
                        all_items.extend(items)
                        logger.debug("grubhub_cat_feed cat=%s items=%s", cat_name, len(items))
                except Exception as e:
                    logger.warning("grubhub_cat_exception cat=%s error=%s", cat_name, e)

            print(f"total_items_fetched={len(all_items)}", flush=True)

            if not all_items:
                print("FAILURE: PARSE_EMPTY\nERROR: 0 items fetched across all categories", flush=True)
                continue

            # ── Step 7: return combined payload in feed format ─────────────────
            payload = {
                "object": {
                    "request_id": str(uuid_mod.uuid4()),
                    "operation_id": str(uuid_mod.uuid4()),
                    "data": {"content": all_items},
                },
                "status": "SUCCESS",
            }

            logger.info("grubhub_fetch_ok attempt=%s slug_id=%s items=%s", attempt, slug_id, len(all_items))
            print("payload_valid=True", flush=True)
            return payload

        except Exception as exc:
            print(f"FAILURE: FETCH_BLOCKED\nERROR: {exc}", flush=True)
            logger.warning("grubhub_fetch_exception attempt=%s url=%s error=%s", attempt, url, exc)

    return None


# =========================================================
# PUBLIC ENTRY
# =========================================================

def fetch_grubhub_menu(
    place: Any,
    *,
    fetcher: FetchCallable | None = None,
) -> Optional[Dict[str, Any]]:
    """
    Fetch and validate a Grubhub menu payload for a place.

    Uses _default_fetcher (curl_cffi → /restaurant_gateway/feed/...) when no
    fetcher is injected. Fetcher remains injectable for tests.
    """
    place_id = getattr(place, "id", None)

    url = _resolve_grubhub_url(place)
    if not url:
        logger.debug("grubhub_no_url place_id=%s", place_id)
        return None

    try:
        raw = fetcher(url) if fetcher is not None else _default_fetcher(url, place=place)
    except Exception as exc:
        logger.warning(
            "grubhub_fetch_failed place_id=%s url=%s error=%s",
            place_id, url, exc,
        )
        return None

    payload = _coerce_payload(raw)
    if not payload:
        logger.debug("grubhub_payload_empty place_id=%s url=%s", place_id, url)
        return None

    if not _looks_like_grubhub_payload(payload):
        logger.debug(
            "grubhub_payload_rejected place_id=%s url=%s keys=%s",
            place_id, url, list(payload.keys())[:10],
        )
        return None

    logger.info("grubhub_payload_valid place_id=%s url=%s", place_id, url)
    return payload


# =========================================================
# URL RESOLUTION
# =========================================================

def _resolve_grubhub_url(place: Any) -> Optional[str]:
    """
    Priority: grubhub_url → menu_source_url → website
    Returns the first that is a valid grubhub.com URL.
    """
    for candidate in (
        getattr(place, "grubhub_url", None),
        getattr(place, "menu_source_url", None),
        getattr(place, "website", None),
    ):
        normalized = _normalize_url(candidate)
        if normalized and _is_grubhub_domain(normalized):
            return normalized
    return None


def _normalize_url(value: Any) -> Optional[str]:
    if not value:
        return None
    try:
        url = str(value).strip()
    except Exception:
        return None
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    return url


def _is_grubhub_domain(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        if host.startswith("www."):
            host = host[4:]
        return host.endswith("grubhub.com")
    except Exception:
        return False


# =========================================================
# PAYLOAD COERCION
# =========================================================

def _coerce_payload(raw: Any) -> Optional[Dict[str, Any]]:
    """Accept dict, JSON string, or bytes. Reject HTML and empty."""
    if raw is None:
        return None
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            return None
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw or raw.startswith("<"):
            return None
        try:
            data = json.loads(raw)
        except Exception:
            return None
        return data if isinstance(data, dict) else None
    return None


# =========================================================
# PAYLOAD VALIDATION
# =========================================================

def _looks_like_grubhub_payload(payload: Dict[str, Any]) -> bool:
    """
    Valid structures:
    - object.data.content  (modern feed endpoint — primary)
    - content (flat list)
    - menu / menus
    - data dict (GraphQL-ish)
    - item-level signals
    """
    # Modern feed: object.data.content
    obj = payload.get("object")
    if isinstance(obj, dict):
        data = obj.get("data")
        if isinstance(data, dict):
            if isinstance(data.get("content"), list):
                return True
            if "menu" in data or "menus" in data:
                return True

    if isinstance(payload.get("content"), list):
        return True
    if isinstance(payload.get("menu"), dict):
        return True
    if isinstance(payload.get("menus"), list):
        return True
    if isinstance(payload.get("data"), dict):
        return True
    if any(k in payload for k in ("item_id", "choice_category_list", "menu_items")):
        return True

    return False
