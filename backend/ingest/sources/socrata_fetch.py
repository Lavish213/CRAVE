from __future__ import annotations

import gzip
import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Socrata Fetch Configuration
# ---------------------------------------------------------

DEFAULT_LIMIT = 50000
REQUEST_TIMEOUT = 60

MAX_RETRIES = 4
BACKOFF_BASE = 2

REQUEST_DELAY = 0.5
REQUEST_JITTER = 0.5

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

NON_JSON_HOST_MARKERS = ("arcgis.com", "hub.arcgis.com")

MAX_DATASET_ROWS = 5_000_000


# ---------------------------------------------------------
# Cache Configuration
# ---------------------------------------------------------

CACHE_ENABLED = True
CACHE_TTL_SECONDS: Optional[int] = None
CACHE_SUFFIX = ".json.gz"

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "health"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _clean_str(value: Any) -> Optional[str]:

    if value is None:
        return None

    value = str(value).strip()

    return value or None


def _safe_int(value: Any) -> Optional[int]:

    if value is None or value == "":
        return None

    try:
        return int(value)
    except Exception:
        return None


def _sleep_with_jitter(base: float) -> None:

    time.sleep(base + random.random() * REQUEST_JITTER)


def _backoff(attempt: int) -> None:

    wait = BACKOFF_BASE ** attempt
    sleep_for = wait + random.random()

    logger.warning(
        "socrata_retry_backoff wait=%s attempt=%s",
        round(sleep_for, 2),
        attempt + 1,
    )

    time.sleep(sleep_for)


# ---------------------------------------------------------
# Cache Helpers
# ---------------------------------------------------------

def _cache_key(
    *,
    domain: str,
    dataset_id: str,
    select: Optional[str],
    where: Optional[str],
    order: Optional[str],
    limit: int,
    max_pages: Optional[int],
) -> str:

    raw = json.dumps(
        {
            "domain": domain,
            "dataset_id": dataset_id,
            "select": select,
            "where": where,
            "order": order,
            "limit": limit,
            "max_pages": max_pages,
        },
        sort_keys=True,
        ensure_ascii=False,
    )

    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _cache_path(
    *,
    domain: str,
    dataset_id: str,
    select: Optional[str],
    where: Optional[str],
    order: Optional[str],
    limit: int,
    max_pages: Optional[int],
) -> Path:

    key = _cache_key(
        domain=domain,
        dataset_id=dataset_id,
        select=select,
        where=where,
        order=order,
        limit=limit,
        max_pages=max_pages,
    )

    return CACHE_DIR / f"{dataset_id}_{key}{CACHE_SUFFIX}"


def _cache_is_valid(path: Path) -> bool:

    if not CACHE_ENABLED or not path.exists():
        return False

    if CACHE_TTL_SECONDS is None:
        return True

    age_seconds = time.time() - path.stat().st_mtime

    return age_seconds < CACHE_TTL_SECONDS


def _load_cache(path: Path) -> Optional[List[Dict[str, Any]]]:

    try:

        with gzip.open(path, "rt", encoding="utf-8") as f:

            data = json.load(f)

        if not isinstance(data, list):

            logger.warning(
                "socrata_cache_invalid_type path=%s type=%s",
                path,
                type(data).__name__,
            )

            path.unlink(missing_ok=True)

            return None

        return data

    except Exception as exc:

        logger.warning("socrata_cache_corrupt path=%s error=%s", path, exc)

        path.unlink(missing_ok=True)

        return None


def _write_cache(path: Path, rows: List[Dict[str, Any]]) -> None:

    try:

        with gzip.open(path, "wt", encoding="utf-8") as f:

            json.dump(rows, f, ensure_ascii=False)

    except Exception as exc:

        logger.warning("socrata_cache_write_failed path=%s error=%s", path, exc)


# ---------------------------------------------------------
# Response Helpers
# ---------------------------------------------------------

def _response_url(response: Any, fallback_url: str) -> str:

    try:
        value = getattr(response, "url", None)

        if value:
            return str(value)

    except Exception:
        pass

    return fallback_url


def _response_content_type(response: Any) -> str:

    try:

        headers = getattr(response, "headers", {}) or {}

        value = headers.get("content-type", "")

        if value:
            return str(value).lower()

    except Exception:
        pass

    return ""


def _looks_like_arcgis_redirect(response: Any, fallback_url: str) -> bool:

    final_url = _response_url(response, fallback_url).lower()

    return any(marker in final_url for marker in NON_JSON_HOST_MARKERS)


# ---------------------------------------------------------
# URL Builder
# ---------------------------------------------------------

def _build_url(
    *,
    domain: str,
    dataset_id: str,
    select: Optional[str],
    where: Optional[str],
    order: Optional[str],
    limit: int,
    offset: int,
) -> str:

    base = f"https://{domain}/resource/{dataset_id}.json"

    params: Dict[str, Any] = {
        "$limit": limit,
        "$offset": offset,
    }

    if order:
        params["$order"] = order

    if select:
        params["$select"] = select

    if where:
        params["$where"] = where

    return f"{base}?{urlencode(params)}"


# ---------------------------------------------------------
# Page Fingerprint
# ---------------------------------------------------------

def _page_fingerprint(rows: List[Dict[str, Any]]) -> str:

    try:

        sample = rows[:10]

        raw = json.dumps(sample, sort_keys=True, ensure_ascii=False)

        return hashlib.md5(raw.encode("utf-8")).hexdigest()

    except Exception:

        return str(len(rows))


# ---------------------------------------------------------
# Page Fetch
# ---------------------------------------------------------

def _fetch_page(
    *,
    url: str,
    app_token: Optional[str],
) -> Optional[List[Dict[str, Any]]]:

    headers: Dict[str, str] = {}

    if app_token:
        headers["X-App-Token"] = app_token

    for attempt in range(MAX_RETRIES):

        try:

            response = fetch(
                url,
                method="GET",
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            )

            status = response.status_code

            if _looks_like_arcgis_redirect(response, url):

                logger.error(
                    "socrata_arcgis_redirect url=%s final_url=%s",
                    url,
                    _response_url(response, url),
                )

                return None

            if status == 200:

                content_type = _response_content_type(response)

                if "json" not in content_type:

                    logger.error(
                        "socrata_non_json_response url=%s content_type=%s",
                        url,
                        content_type,
                    )

                    return None

                data = response.json()

                if not isinstance(data, list):

                    logger.error(
                        "socrata_invalid_response url=%s type=%s",
                        url,
                        type(data).__name__,
                    )

                    return None

                return data

            if status in RETRYABLE_STATUS_CODES:

                logger.warning(
                    "socrata_retry_status code=%s url=%s attempt=%s",
                    status,
                    url,
                    attempt + 1,
                )

                _backoff(attempt)

                continue

            logger.error(
                "socrata_bad_status code=%s url=%s",
                status,
                url,
            )

            return None

        except Exception as exc:

            logger.warning(
                "socrata_fetch_error url=%s attempt=%s error=%s",
                url,
                attempt + 1,
                exc,
            )

            _backoff(attempt)

    logger.error("socrata_fetch_failed url=%s", url)

    return None


# ---------------------------------------------------------
# Public Fetch Engine
# ---------------------------------------------------------

def fetch_socrata_dataset(
    *,
    domain: str,
    dataset_id: str,
    app_token: Optional[str] = None,
    select: Optional[str] = None,
    where: Optional[str] = None,
    limit: int = DEFAULT_LIMIT,
    max_pages: Optional[int] = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:

    if limit <= 0:
        raise ValueError("limit must be > 0")

    order = ":id"

    cache_path = _cache_path(
        domain=domain,
        dataset_id=dataset_id,
        select=select,
        where=where,
        order=order,
        limit=limit,
        max_pages=max_pages,
    )

    logger.info(
        "socrata_fetch_start dataset=%s domain=%s limit=%s max_pages=%s",
        dataset_id,
        domain,
        limit,
        max_pages,
    )

    if use_cache and not force_refresh and _cache_is_valid(cache_path):

        cached = _load_cache(cache_path)

        if cached is not None:

            logger.info(
                "socrata_cache_hit dataset=%s rows=%s",
                dataset_id,
                len(cached),
            )

            return cached

    results: List[Dict[str, Any]] = []

    page = 0
    offset = 0

    seen_pages = set()

    while True:

        if max_pages is not None and page >= max_pages:

            logger.info("socrata_max_pages_reached pages=%s", page)

            break

        url = _build_url(
            domain=domain,
            dataset_id=dataset_id,
            select=select,
            where=where,
            order=order,
            limit=limit,
            offset=offset,
        )

        logger.info(
            "socrata_fetch_page dataset=%s page=%s offset=%s",
            dataset_id,
            page,
            offset,
        )

        rows = _fetch_page(url=url, app_token=app_token)

        if rows is None:

            logger.warning(
                "socrata_page_failed dataset=%s offset=%s",
                dataset_id,
                offset,
            )

            break

        fingerprint = _page_fingerprint(rows)

        if fingerprint in seen_pages:

            logger.warning(
                "socrata_duplicate_page_detected dataset=%s page=%s",
                dataset_id,
                page,
            )

            break

        seen_pages.add(fingerprint)

        results.extend(rows)

        if len(results) > MAX_DATASET_ROWS:

            logger.error(
                "socrata_dataset_exceeds_max rows=%s",
                len(results),
            )

            break

        if len(rows) < limit:

            logger.info(
                "socrata_dataset_complete dataset=%s rows=%s pages=%s",
                dataset_id,
                len(results),
                page + 1,
            )

            break

        page += 1
        offset += limit

        _sleep_with_jitter(REQUEST_DELAY)

    if use_cache and results:

        _write_cache(cache_path, results)

        logger.info(
            "socrata_cache_saved dataset=%s rows=%s",
            dataset_id,
            len(results),
        )

    logger.info(
        "socrata_fetch_complete dataset=%s rows=%s pages=%s",
        dataset_id,
        len(results),
        page + 1,
    )

    return results