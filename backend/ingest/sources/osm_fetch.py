from __future__ import annotations

import gzip
import hashlib
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

from app.services.network.http_fetcher import fetch


logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Overpass Servers
# ---------------------------------------------------------

OVERPASS_SERVERS: List[str] = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

SERVER_COOLDOWN_SECONDS = 120
_server_cooldowns: Dict[str, float] = {}

# ---------------------------------------------------------
# Fetch Configuration
# ---------------------------------------------------------

REQUEST_TIMEOUT = 60
MAX_RETRIES_PER_SERVER = 4

REQUEST_DELAY_SECONDS = 1.25
REQUEST_JITTER_SECONDS = 0.35

RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}
BACKOFF_SCHEDULE_SECONDS = [2, 5, 10, 20]

# ---------------------------------------------------------
# Tile Configuration
# ---------------------------------------------------------

TILE_STEP = 0.03

# ---------------------------------------------------------
# Cache Configuration
# ---------------------------------------------------------

CACHE_ENABLED = True
CACHE_TTL_SECONDS: Optional[int] = None
CACHE_COMPRESSION_SUFFIX = ".json.gz"

CACHE_DIR = Path(__file__).resolve().parents[2] / "data" / "osm_tiles"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------
# Record Configuration
# ---------------------------------------------------------

DEFAULT_SOURCE = "osm"
DEFAULT_CONFIDENCE = 0.6
MIN_PHONE_DIGITS = 7

# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _clean_string(value: Optional[Any]) -> Optional[str]:
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def _safe_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None

    try:
        return float(value)
    except Exception:
        return None


def _normalize_phone(phone: Optional[str]) -> Optional[str]:
    phone = _clean_string(phone)

    if not phone:
        return None

    normalized = re.sub(r"[^\d+]", "", phone)

    if len(normalized.replace("+", "")) < MIN_PHONE_DIGITS:
        return None

    return normalized


def _normalize_website(url: Optional[str]) -> Optional[str]:
    url = _clean_string(url)

    if not url:
        return None

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    return url


def _sleep_with_jitter(base_seconds: float) -> None:
    sleep_for = base_seconds + random.uniform(0.0, REQUEST_JITTER_SECONDS)
    time.sleep(max(0.0, sleep_for))


# ---------------------------------------------------------
# Cache Helpers
# ---------------------------------------------------------

def _tile_cache_key(tile: Tuple[float, float, float, float]) -> str:
    lat_min, lon_min, lat_max, lon_max = tile
    raw = f"{lat_min:.6f}|{lon_min:.6f}|{lat_max:.6f}|{lon_max:.6f}|{TILE_STEP:.4f}"
    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def _tile_cache_path(tile: Tuple[float, float, float, float]) -> Path:
    key = _tile_cache_key(tile)
    return CACHE_DIR / f"tile_{key}{CACHE_COMPRESSION_SUFFIX}"


def _cache_is_valid(path: Path) -> bool:
    if not CACHE_ENABLED or not path.exists():
        return False

    if CACHE_TTL_SECONDS is None:
        return True

    age_seconds = time.time() - path.stat().st_mtime
    return age_seconds < CACHE_TTL_SECONDS


def _load_tile_cache(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logger.warning("osm_tile_cache_corrupt path=%s", path)
        path.unlink(missing_ok=True)
        return None


def _write_tile_cache(path: Path, data: Dict[str, Any]) -> None:
    try:
        with gzip.open(path, "wt", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception as exc:
        logger.warning("osm_tile_cache_write_failed path=%s error=%s", path, exc)


# ---------------------------------------------------------
# Address Builder
# ---------------------------------------------------------

def _build_address(tags: Dict[str, Any]) -> Optional[str]:
    full = _clean_string(tags.get("addr:full"))
    if full:
        return full

    number = _clean_string(tags.get("addr:housenumber"))
    street = _clean_string(tags.get("addr:street"))
    city = _clean_string(tags.get("addr:city"))

    parts = [part for part in (number, street, city) if part]
    return " ".join(parts) or None


# ---------------------------------------------------------
# Category Detection
# ---------------------------------------------------------

def _category_hint(tags: Dict[str, Any]) -> Optional[str]:
    for key in ("amenity", "shop", "tourism", "craft"):
        value = _clean_string(tags.get(key))
        if value:
            return value

    cuisine = _clean_string(tags.get("cuisine"))
    if cuisine:
        return cuisine.split(";", 1)[0].strip()

    return None


# ---------------------------------------------------------
# Bounding Box Tiling
# ---------------------------------------------------------

def _tile_bbox(
    lat_min: float,
    lon_min: float,
    lat_max: float,
    lon_max: float,
    step: float = TILE_STEP,
) -> Iterable[Tuple[float, float, float, float]]:
    lat = lat_min

    while lat < lat_max:
        next_lat = min(lat + step, lat_max)
        lon = lon_min

        while lon < lon_max:
            next_lon = min(lon + step, lon_max)
            yield lat, lon, next_lat, next_lon
            lon = next_lon

        lat = next_lat


# ---------------------------------------------------------
# Overpass Query
# ---------------------------------------------------------

def _build_query(lat_min: float, lon_min: float, lat_max: float, lon_max: float) -> str:
    return f"""
[out:json][timeout:60];
(
  node["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court|ice_cream|biergarten|takeaway|food_truck"]({lat_min},{lon_min},{lat_max},{lon_max});
  way["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court|ice_cream|biergarten|takeaway|food_truck"]({lat_min},{lon_min},{lat_max},{lon_max});
  relation["amenity"~"restaurant|fast_food|cafe|bar|pub|food_court|ice_cream|biergarten|takeaway|food_truck"]({lat_min},{lon_min},{lat_max},{lon_max});

  node["shop"~"bakery|deli|pastry|confectionery|butcher|cheese|greengrocer|supermarket|convenience"]({lat_min},{lon_min},{lat_max},{lon_max});
  way["shop"~"bakery|deli|pastry|confectionery|butcher|cheese|greengrocer|supermarket|convenience"]({lat_min},{lon_min},{lat_max},{lon_max});

  node["cuisine"]({lat_min},{lon_min},{lat_max},{lon_max});
  way["cuisine"]({lat_min},{lon_min},{lat_max},{lon_max});
  relation["cuisine"]({lat_min},{lon_min},{lat_max},{lon_max});
);
out center tags;
""".strip()


# ---------------------------------------------------------
# Overpass Fetch Wrapper
# ---------------------------------------------------------

def _server_available(server: str) -> bool:
    cooldown_until = _server_cooldowns.get(server)
    return not cooldown_until or time.time() >= cooldown_until


def _mark_server_cooldown(server: str) -> None:
    _server_cooldowns[server] = time.time() + SERVER_COOLDOWN_SECONDS


def _fetch_overpass(query: str) -> Optional[Dict[str, Any]]:
    servers = list(OVERPASS_SERVERS)
    random.shuffle(servers)

    for server in servers:
        if not _server_available(server):
            logger.warning("osm_server_cooldown_active server=%s", server)
            continue

        for attempt in range(MAX_RETRIES_PER_SERVER):
            try:
                response = fetch(
                    server,
                    method="POST",
                    data=query,
                    timeout=REQUEST_TIMEOUT,
                )

                if response.status_code == 200:
                    try:
                        return response.json()
                    except Exception:
                        logger.warning("osm_invalid_json_response server=%s", server)
                        break

                if response.status_code in RETRYABLE_STATUS_CODES:
                    backoff = BACKOFF_SCHEDULE_SECONDS[min(attempt, len(BACKOFF_SCHEDULE_SECONDS) - 1)]

                    logger.warning(
                        "osm_fetch_retryable_status server=%s status=%s attempt=%s backoff=%s",
                        server,
                        response.status_code,
                        attempt + 1,
                        backoff,
                    )

                    _sleep_with_jitter(backoff)
                    continue

                logger.warning(
                    "osm_fetch_bad_status server=%s status=%s",
                    server,
                    response.status_code,
                )
                break

            except Exception as exc:
                backoff = BACKOFF_SCHEDULE_SECONDS[min(attempt, len(BACKOFF_SCHEDULE_SECONDS) - 1)]

                logger.warning(
                    "osm_fetch_failed server=%s attempt=%s backoff=%s error=%s",
                    server,
                    attempt + 1,
                    backoff,
                    exc,
                )

                _sleep_with_jitter(backoff)

        _mark_server_cooldown(server)
        logger.warning("osm_switching_overpass_server next_server=%s", server)

    return None


# ---------------------------------------------------------
# Element Parsing
# ---------------------------------------------------------

def _element_lat_lon(element: Dict[str, Any]) -> Tuple[Optional[float], Optional[float]]:
    lat = _safe_float(element.get("lat"))
    lon = _safe_float(element.get("lon"))

    if lat is not None and lon is not None:
        return lat, lon

    center = element.get("center") or {}
    return _safe_float(center.get("lat")), _safe_float(center.get("lon"))


def _element_external_id(element: Dict[str, Any]) -> Optional[str]:
    element_id = element.get("id")
    element_type = _clean_string(element.get("type"))

    if element_id is None or not element_type:
        return None

    return f"osm:{element_type}:{element_id}"


# ---------------------------------------------------------
# OSM Fetch
# ---------------------------------------------------------

def fetch_osm_pois(
    *,
    lat_min: float,
    lat_max: float,
    lon_min: float,
    lon_max: float,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()

    tile_count = 0
    cache_hits = 0
    cache_misses = 0
    skipped_missing_name = 0
    skipped_missing_coords = 0
    skipped_missing_id = 0
    skipped_duplicates = 0

    for tile in _tile_bbox(lat_min, lon_min, lat_max, lon_max):
        tile_count += 1
        cache_path = _tile_cache_path(tile)

        logger.info("osm_fetch_tile tile=%s bbox=%s", tile_count, tile)

        data: Optional[Dict[str, Any]] = None

        if _cache_is_valid(cache_path):
            data = _load_tile_cache(cache_path)
            if data is not None:
                cache_hits += 1
                logger.info("osm_tile_cache_hit tile=%s path=%s", tile_count, cache_path.name)

        if data is None:
            cache_misses += 1
            data = _fetch_overpass(_build_query(*tile))

            if data is None:
                logger.warning("osm_fetch_tile_failed tile=%s", tile_count)
                continue

            _write_tile_cache(cache_path, data)
            logger.info("osm_tile_cache_saved tile=%s path=%s", tile_count, cache_path.name)

        for element in data.get("elements", []):
            tags = element.get("tags") or {}

            # Skip unnamed POIs early to avoid NOT NULL failures later.
            name = _clean_string(tags.get("name"))
            if not name:
                skipped_missing_name += 1
                continue

            item_lat, item_lon = _element_lat_lon(element)
            if item_lat is None or item_lon is None:
                skipped_missing_coords += 1
                continue

            external_id = _element_external_id(element)
            if not external_id:
                skipped_missing_id += 1
                continue

            if external_id in seen_ids:
                skipped_duplicates += 1
                continue

            seen_ids.add(external_id)

            record = {
                "external_id": external_id,
                "name": name,
                "address": _build_address(tags),
                "lat": item_lat,
                "lon": item_lon,
                "phone": _normalize_phone(tags.get("phone")),
                "website": _normalize_website(tags.get("website")),
                "category_hint": _category_hint(tags),
                "source": DEFAULT_SOURCE,
                "confidence": DEFAULT_CONFIDENCE,
                "raw_payload": {
                    "id": element.get("id"),
                    "type": element.get("type"),
                    "lat": item_lat,
                    "lon": item_lon,
                    "tags": tags,
                },
            }

            results.append(record)

        _sleep_with_jitter(REQUEST_DELAY_SECONDS)

    logger.info(
        "osm_pois_fetched count=%s tiles=%s cache_hits=%s cache_misses=%s",
        len(results),
        tile_count,
        cache_hits,
        cache_misses,
    )

    logger.info(
        "osm_fetch_summary skipped_missing_name=%s skipped_missing_coords=%s skipped_missing_id=%s skipped_duplicates=%s",
        skipped_missing_name,
        skipped_missing_coords,
        skipped_missing_id,
        skipped_duplicates,
    )

    return results