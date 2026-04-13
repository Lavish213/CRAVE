from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path
from typing import Dict, Optional


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Config
# ---------------------------------------------------------

CACHE_TTL_SECONDS = 60 * 60 * 24
MAX_MEMORY_ENTRIES = 2000
MAX_BUNDLE_SIZE = 2_000_000  # ~2MB safety cap (prevents memory abuse)

CACHE_DIR = (
    Path(__file__).resolve().parents[4]
    / "data"
    / "cache"
    / "js_bundles"
)

CACHE_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------
# Memory Cache (O(1) eviction tracking)
# ---------------------------------------------------------

_memory_cache: Dict[str, Dict] = {}
_memory_order: Dict[str, float] = {}  # key → timestamp


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------

def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _is_expired(ts: float) -> bool:
    return (time.time() - ts) > CACHE_TTL_SECONDS


def _cache_file(key: str) -> Path:
    return CACHE_DIR / f"{key}.cache"


def _ts_file(key: str) -> Path:
    return CACHE_DIR / f"{key}.ts"


# ---------------------------------------------------------
# Memory Cache
# ---------------------------------------------------------

def get_memory(key: str) -> Optional[str]:

    entry = _memory_cache.get(key)

    if not entry:
        return None

    ts = entry.get("ts")

    if not ts or _is_expired(ts):
        _memory_cache.pop(key, None)
        _memory_order.pop(key, None)
        return None

    return entry.get("value")


def set_memory(key: str, value: str):

    if not value:
        return

    if len(value) > MAX_BUNDLE_SIZE:
        return  # prevent massive bundles killing memory

    now = time.time()

    # Evict oldest if needed (O(n) → O(1) behavior with tracking)
    if len(_memory_cache) >= MAX_MEMORY_ENTRIES:

        try:
            oldest_key = min(_memory_order, key=_memory_order.get)
            _memory_cache.pop(oldest_key, None)
            _memory_order.pop(oldest_key, None)
        except Exception:
            _memory_cache.clear()
            _memory_order.clear()

    _memory_cache[key] = {
        "value": value,
        "ts": now,
    }

    _memory_order[key] = now


# ---------------------------------------------------------
# Disk Cache
# ---------------------------------------------------------

def get_disk(key: str) -> Optional[str]:

    file_path = _cache_file(key)
    ts_path = _ts_file(key)

    if not file_path.exists():
        return None

    try:

        # Timestamp validation
        if ts_path.exists():

            try:
                ts = float(ts_path.read_text())
            except Exception:
                ts = 0

            if not ts or _is_expired(ts):
                file_path.unlink(missing_ok=True)
                ts_path.unlink(missing_ok=True)
                return None

        data = file_path.read_text()

        if not data:
            return None

        if len(data) > MAX_BUNDLE_SIZE * 2:
            # Corrupt / suspicious
            file_path.unlink(missing_ok=True)
            ts_path.unlink(missing_ok=True)
            return None

        return data

    except Exception as exc:

        logger.debug(
            "js_bundle_disk_cache_read_failed key=%s error=%s",
            key,
            exc,
        )

        return None


def set_disk(key: str, value: str):

    if not value:
        return

    if len(value) > MAX_BUNDLE_SIZE * 3:
        return  # skip insane bundles

    try:

        file_path = _cache_file(key)
        ts_path = _ts_file(key)

        temp_file = file_path.with_suffix(".tmp")

        # atomic write
        temp_file.write_text(value)
        temp_file.replace(file_path)

        ts_path.write_text(str(time.time()))

    except Exception as exc:

        logger.debug(
            "js_bundle_disk_cache_write_failed key=%s error=%s",
            key,
            exc,
        )


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def get_bundle(bundle_url: str) -> Optional[str]:

    if not bundle_url:
        return None

    key = _hash_key(bundle_url)

    # Memory first (fast path)
    cached = get_memory(key)

    if cached:
        return cached

    # Disk fallback
    cached = get_disk(key)

    if cached:
        set_memory(key, cached)
        return cached

    return None


def store_bundle(bundle_url: str, bundle_text: str):

    if not bundle_url or not bundle_text:
        return

    key = _hash_key(bundle_url)

    set_memory(key, bundle_text)
    set_disk(key, bundle_text)