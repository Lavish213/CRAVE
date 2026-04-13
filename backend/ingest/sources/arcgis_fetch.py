from __future__ import annotations

import gzip
import hashlib
import json
import logging
import random
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

from app.services.network.http_fetcher import fetch

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# CONFIG
# ---------------------------------------------------------

DEFAULT_LIMIT = 1000
SAFE_MAX_LIMIT = 1000
REQUEST_TIMEOUT = 60

MAX_RETRIES = 5
BACKOFF_BASE = 2

REQUEST_DELAY = 0.3
REQUEST_JITTER = 0.3

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
MAX_DATASET_ROWS = 5_000_000

META_CACHE: Dict[str, Dict[str, Any]] = {}

OBJECT_ID_FIELDS = (
    "OBJECTID", "ObjectId", "objectid", "object_id",
    "FID", "fid", "GlobalID", "globalid", "id", "ID"
)

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "arcgis"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# UTILS
# ---------------------------------------------------------

def _sleep():
    time.sleep(REQUEST_DELAY + random.random() * REQUEST_JITTER)

def _backoff(attempt: int):
    wait = BACKOFF_BASE ** attempt + random.random()
    logger.warning("retry_backoff wait=%s", round(wait, 2))
    time.sleep(wait)

def _clean(v):
    if v is None:
        return None
    v = str(v).strip()
    return v or None

def _safe_int(v):
    try:
        return int(v)
    except:
        return None

def _safe_float(v):
    try:
        return float(v)
    except:
        return None

def _normalize_where(w):
    w = _clean(w)
    return "1=1" if not w else w

def _normalize_limit(l):
    try:
        return min(int(l), SAFE_MAX_LIMIT)
    except:
        return SAFE_MAX_LIMIT

# ---------------------------------------------------------
# METADATA
# ---------------------------------------------------------

def _detect_metadata(url: str) -> Dict[str, Any]:
    try:
        parsed = urlparse(url)
        meta_url = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.replace("/query", ""),
            "",
            "f=json",
            "",
        ))

        r = fetch(meta_url, method="GET", timeout=30)

        if r.status_code != 200:
            return {}

        return r.json() if isinstance(r.json(), dict) else {}

    except Exception:
        return {}

def _get_object_id_field(meta):
    fields = meta.get("fields") or []

    for f in fields:
        if "oid" in str(f.get("type", "")).lower():
            return f.get("name")

    for f in fields:
        if f.get("name") in OBJECT_ID_FIELDS:
            return f.get("name")

    return meta.get("objectIdField")

def _get_limit(meta):
    return min(meta.get("maxRecordCount", DEFAULT_LIMIT), SAFE_MAX_LIMIT)

# ---------------------------------------------------------
# CACHE
# ---------------------------------------------------------

def _cache_path(url, where, limit):
    key = hashlib.md5(f"{url}-{where}-{limit}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.json.gz"

def _load_cache(p):
    try:
        with gzip.open(p, "rt") as f:
            return json.load(f)
    except:
        return None

def _save_cache(p, data):
    try:
        with gzip.open(p, "wt") as f:
            json.dump(data, f)
    except:
        pass

# ---------------------------------------------------------
# FETCH PAGE
# ---------------------------------------------------------

def _fetch_page(url):
    for i in range(MAX_RETRIES):
        try:
            r = fetch(url, method="GET", timeout=REQUEST_TIMEOUT)

            if r.status_code == 200:
                data = r.json()

                if not isinstance(data, dict):
                    return None

                if data.get("error"):
                    return None

                feats = data.get("features") or []

                rows = []
                for f in feats:
                    attrs = f.get("attributes", {}) or {}
                    geom = f.get("geometry")

                    if geom:
                        if "x" in geom and "y" in geom:
                            attrs["_geometry_x"] = geom["x"]
                            attrs["_geometry_y"] = geom["y"]

                    rows.append(attrs)

                return rows

            if r.status_code in RETRYABLE_STATUS_CODES:
                _backoff(i)
                continue

            return None

        except Exception:
            _backoff(i)

    return None

# ---------------------------------------------------------
# URL BUILDER (FIXED)
# ---------------------------------------------------------

def _build_url(base_url, where, limit, offset=None, order=None):

    parsed = urlparse(base_url)
    params = dict(parse_qsl(parsed.query))

    params.update({
        "where": where,
        "outFields": "*",
        "returnGeometry": "true",
        "f": "json",
    })

    # 🔥 CRITICAL FIX: only include ONE pagination method
    if order:
        params["orderByFields"] = order
    else:
        params["resultRecordCount"] = limit

        if offset:
            params["resultOffset"] = offset

    query = urlencode(params).replace("%2A", "*")

    return urlunparse((
        parsed.scheme,
        parsed.netloc,
        parsed.path,
        "",
        query,
        ""
    ))

# ---------------------------------------------------------
# MAIN FETCH
# ---------------------------------------------------------

def fetch_arcgis_dataset(
    base_url: str,
    where: str = "1=1",
    limit: Optional[int] = None,
    use_cache: bool = True,
    force_refresh: bool = False,
) -> List[Dict[str, Any]]:

    logger.info("arcgis_start url=%s", base_url)

    where = _normalize_where(where)

    meta = META_CACHE.get(base_url) or _detect_metadata(base_url)
    META_CACHE[base_url] = meta

    limit = _normalize_limit(limit or _get_limit(meta))

    cache = _cache_path(base_url, where, limit)

    if use_cache and not force_refresh and cache.exists():
        data = _load_cache(cache)
        if data:
            logger.info("cache_hit rows=%s", len(data))
            return data

    results = []
    seen_ids = set()

    object_id_field = _get_object_id_field(meta)
    use_objectid = False
    last_id = None

    offset = 0
    page = 0

    while True:

        if use_objectid and object_id_field and last_id is not None:
            where_clause = f"{object_id_field} > {last_id}"
            url = _build_url(base_url, where_clause, limit, order=object_id_field)
        else:
            url = _build_url(base_url, where, limit, offset=offset)

        rows = _fetch_page(url)

        if rows is None:
            # 🔥 fallback switch
            if object_id_field and not use_objectid:
                logger.warning("switching_to_objectid")
                use_objectid = True
                results = []
                seen_ids.clear()
                last_id = None
                continue
            break

        if not rows:
            break

        new_rows = []

        for r in rows:
            rid = next((r.get(f) for f in OBJECT_ID_FIELDS if r.get(f)), None)

            if rid and rid in seen_ids:
                continue

            if rid:
                seen_ids.add(rid)
                last_id = max(last_id or 0, int(rid))

            new_rows.append(r)

        if not new_rows:
            break

        results.extend(new_rows)

        if len(rows) < limit:
            break

        offset += limit
        page += 1
        _sleep()

    if use_cache and results:
        _save_cache(cache, results)

    logger.info("arcgis_done rows=%s", len(results))

    return results