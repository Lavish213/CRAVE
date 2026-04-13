from __future__ import annotations

import json
import logging
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


MAX_ENDPOINTS_PER_DOMAIN = 25
MAX_DOMAINS = 500
MEMORY_TTL_SECONDS = 7 * 24 * 60 * 60
MEMORY_DIR = Path("backend/runtime/menu_memory")
MEMORY_FILE = MEMORY_DIR / "js_endpoint_memory.json"


_LOCK = threading.RLock()
_CACHE: dict[str, dict[str, Any]] | None = None


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _utc_ts() -> int:
    return int(time.time())


def _clean_text(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:
        text = str(value).strip()
    except Exception:
        return None

    return text or None


def _domain_from_url(url: Optional[str]) -> Optional[str]:
    clean = _clean_text(url)
    if not clean:
        return None

    try:
        domain = urlparse(clean).netloc.lower().strip()
    except Exception:
        return None

    return domain or None


def _normalize_method(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return "GET"
    return text.upper()


def _safe_body(value: Any) -> Optional[dict[str, Any]]:
    if isinstance(value, dict):
        return value
    return None


def _endpoint_key(endpoint: dict[str, Any]) -> str:
    url = _clean_text(endpoint.get("url")) or ""
    method = _normalize_method(endpoint.get("method"))
    body = _safe_body(endpoint.get("body"))

    try:
        body_key = json.dumps(body, sort_keys=True, separators=(",", ":")) if body else ""
    except Exception:
        body_key = ""

    return f"{method}|{url}|{body_key}"


def _score_value(endpoint: dict[str, Any]) -> int:
    try:
        return int(endpoint.get("score") or 0)
    except Exception:
        return 0


def _make_parent_dir() -> None:
    MEMORY_DIR.mkdir(parents=True, exist_ok=True)


def _safe_load_file() -> dict[str, Any]:
    if not MEMORY_FILE.exists():
        return {}

    try:
        raw = MEMORY_FILE.read_text(encoding="utf-8")
    except Exception as exc:
        logger.debug("js_endpoint_memory_read_failed error=%s", exc)
        return {}

    if not raw.strip():
        return {}

    try:
        data = json.loads(raw)
    except Exception as exc:
        logger.debug("js_endpoint_memory_json_failed error=%s", exc)
        return {}

    if not isinstance(data, dict):
        return {}

    return data


def _safe_write_file(data: dict[str, Any]) -> None:
    try:
        _make_parent_dir()
        tmp = MEMORY_FILE.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2),
            encoding="utf-8",
        )
        tmp.replace(MEMORY_FILE)
    except Exception as exc:
        logger.debug("js_endpoint_memory_write_failed error=%s", exc)


def _get_cache() -> dict[str, dict[str, Any]]:
    global _CACHE

    with _LOCK:
        if _CACHE is None:
            loaded = _safe_load_file()
            normalized: dict[str, dict[str, Any]] = {}

            for domain, payload in loaded.items():
                if not isinstance(domain, str) or not isinstance(payload, dict):
                    continue
                normalized[domain] = payload

            _CACHE = normalized

        return _CACHE


def _prune_expired_locked(cache: dict[str, dict[str, Any]]) -> None:
    now = _utc_ts()
    expired_domains: list[str] = []

    for domain, payload in cache.items():
        updated_at = payload.get("updated_at")
        try:
            updated_ts = int(updated_at or 0)
        except Exception:
            updated_ts = 0

        if not updated_ts or (now - updated_ts) > MEMORY_TTL_SECONDS:
            expired_domains.append(domain)

    for domain in expired_domains:
        cache.pop(domain, None)

    if len(cache) <= MAX_DOMAINS:
        return

    ordered = sorted(
        cache.items(),
        key=lambda kv: int(kv[1].get("updated_at") or 0),
        reverse=True,
    )

    keep = dict(ordered[:MAX_DOMAINS])
    cache.clear()
    cache.update(keep)


def _normalize_endpoint(endpoint: dict[str, Any]) -> Optional[dict[str, Any]]:
    if not isinstance(endpoint, dict):
        return None

    url = _clean_text(endpoint.get("url"))
    if not url:
        return None

    normalized = {
        "url": url,
        "method": _normalize_method(endpoint.get("method")),
        "score": _score_value(endpoint),
    }

    body = _safe_body(endpoint.get("body"))
    if body:
        normalized["body"] = body

    return normalized


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def get_remembered_endpoints(url: str) -> List[Dict[str, Any]]:
    domain = _domain_from_url(url)
    if not domain:
        return []

    with _LOCK:
        cache = _get_cache()
        _prune_expired_locked(cache)

        payload = cache.get(domain)
        if not payload:
            return []

        endpoints = payload.get("endpoints")
        if not isinstance(endpoints, list):
            return []

        normalized: list[dict[str, Any]] = []

        for endpoint in endpoints:
            item = _normalize_endpoint(endpoint)
            if item:
                normalized.append(item)

        logger.debug(
            "js_endpoint_memory_hit domain=%s count=%s",
            domain,
            len(normalized),
        )

        return normalized


def remember_endpoints(
    url: str,
    endpoints: List[Dict[str, Any]],
) -> int:
    domain = _domain_from_url(url)
    if not domain or not endpoints:
        return 0

    with _LOCK:
        cache = _get_cache()
        _prune_expired_locked(cache)

        existing_payload = cache.get(domain) or {}
        existing_endpoints = existing_payload.get("endpoints")
        if not isinstance(existing_endpoints, list):
            existing_endpoints = []

        merged: list[dict[str, Any]] = []
        seen: set[str] = set()

        for endpoint in existing_endpoints:
            item = _normalize_endpoint(endpoint)
            if not item:
                continue
            key = _endpoint_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)

        for endpoint in endpoints:
            item = _normalize_endpoint(endpoint)
            if not item:
                continue
            key = _endpoint_key(item)
            if key in seen:
                continue
            seen.add(key)
            merged.append(item)

        merged.sort(
            key=lambda item: (
                _score_value(item),
                1 if item.get("method") == "POST" else 0,
                -len(item.get("url", "")),
            ),
            reverse=True,
        )

        merged = merged[:MAX_ENDPOINTS_PER_DOMAIN]

        cache[domain] = {
            "domain": domain,
            "updated_at": _utc_ts(),
            "endpoints": merged,
        }

        _prune_expired_locked(cache)
        _safe_write_file(cache)

        logger.info(
            "js_endpoint_memory_saved domain=%s count=%s",
            domain,
            len(merged),
        )

        return len(merged)


def clear_endpoint_memory(url: Optional[str] = None) -> None:
    global _CACHE

    with _LOCK:
        if url:
            domain = _domain_from_url(url)
            if not domain:
                return

            cache = _get_cache()
            cache.pop(domain, None)
            _safe_write_file(cache)

            logger.info("js_endpoint_memory_cleared domain=%s", domain)
            return

        _CACHE = {}
        _safe_write_file({})
        logger.info("js_endpoint_memory_cleared_all")