from __future__ import annotations

import json
import logging
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


FetchCallable = Callable[[str], Any]


# =========================================================
# PUBLIC ENTRY
# =========================================================

def fetch_grubhub_menu(
    place: Any,
    *,
    fetcher: FetchCallable | None = None,
) -> Optional[Dict[str, Any]]:
    """
    🔥 FINAL PRODUCTION GRUBHUB FETCHER

    Responsibilities:
    - resolve correct Grubhub URL
    - fetch raw payload via injected transport
    - normalize response → dict
    - validate payload shape

    DOES NOT:
    - parse menu (handled later)
    - hardcode network logic (injectable)
    """

    place_id = getattr(place, "id", None)

    url = _resolve_grubhub_url(place)
    if not url:
        logger.debug("grubhub_no_url place_id=%s", place_id)
        return None

    if fetcher is None:
        logger.debug("grubhub_no_fetcher url=%s", url)
        return None

    try:
        raw = fetcher(url)
    except Exception as exc:
        logger.warning(
            "grubhub_fetch_failed place_id=%s url=%s error=%s",
            place_id,
            url,
            exc,
        )
        return None

    payload = _coerce_payload(raw)

    if not payload:
        logger.debug(
            "grubhub_payload_empty place_id=%s url=%s",
            place_id,
            url,
        )
        return None

    if not _looks_like_grubhub_payload(payload):
        logger.debug(
            "grubhub_payload_rejected place_id=%s url=%s keys=%s",
            place_id,
            url,
            list(payload.keys())[:10],
        )
        return None

    logger.info(
        "grubhub_payload_valid place_id=%s url=%s",
        place_id,
        url,
    )

    return payload


# =========================================================
# URL RESOLUTION
# =========================================================

def _resolve_grubhub_url(place: Any) -> Optional[str]:
    """
    Priority:
    1. grubhub_url
    2. menu_source_url
    3. website
    """

    candidates = (
        getattr(place, "grubhub_url", None),
        getattr(place, "menu_source_url", None),
        getattr(place, "website", None),
    )

    for candidate in candidates:
        normalized = _normalize_url(candidate)

        if not normalized:
            continue

        if _is_grubhub_domain(normalized):
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
        parsed = urlparse(url)
        host = parsed.netloc.lower()

        if host.startswith("www."):
            host = host[4:]

        return host.endswith("grubhub.com")

    except Exception:
        return False


# =========================================================
# PAYLOAD COERCION
# =========================================================

def _coerce_payload(raw: Any) -> Optional[Dict[str, Any]]:
    """
    Accept:
    - dict
    - JSON string
    - bytes

    Reject:
    - HTML
    - empty
    """

    if raw is None:
        return None

    # Already dict
    if isinstance(raw, dict):
        return raw

    # bytes → str
    if isinstance(raw, bytes):
        try:
            raw = raw.decode("utf-8", errors="ignore")
        except Exception:
            return None

    # string → JSON
    if isinstance(raw, str):
        raw = raw.strip()

        if not raw:
            return None

        # ❗ Detect HTML (common failure case)
        if raw.startswith("<"):
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
    Flexible validation across:
    - legacy Grubhub JSON
    - modern GraphQL-ish payloads
    - menu/content structures
    """

    # Common structure
    if "object" in payload and isinstance(payload["object"], dict):
        data = payload["object"].get("data")

        if isinstance(data, dict):
            if isinstance(data.get("content"), list):
                return True

            if "menu" in data or "menus" in data:
                return True

    # Flat menu-like structures
    if isinstance(payload.get("content"), list):
        return True

    if isinstance(payload.get("menu"), dict):
        return True

    if isinstance(payload.get("menus"), list):
        return True

    # GraphQL-ish
    if isinstance(payload.get("data"), dict):
        return True

    # Loose fallback (IDs + menu signals)
    if any(k in payload for k in ("item_id", "choice_category_list", "menu_items")):
        return True

    return False