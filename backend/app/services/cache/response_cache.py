"""
Tiered cache: Redis (shared, L1) → in-memory (per-process, L2).

Behavior:
- Redis UP:   reads/writes go to Redis; also written to local for process-local speed.
- Redis DOWN: all operations use in-memory only.
- Redis failures never propagate — always fail open.

Invalidation:
- delete/delete_prefix hit BOTH Redis and local so stale local data is cleared.

Interface unchanged from original ResponseCache — all call sites unaffected.
"""
from __future__ import annotations

import time
from threading import RLock
from typing import Any, Dict, Optional, Tuple

from app.services.cache.redis_client import (
    redis_delete,
    redis_delete_prefix,
    redis_get,
    redis_set,
)


DEFAULT_TTL = 60
MAX_KEYS = 50_000


class ResponseCache:

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = RLock()

    # ─────────────────────────────────────────────────────────────────
    # GET  — Redis first, local fallback
    # ─────────────────────────────────────────────────────────────────

    def get(self, key: str) -> Optional[Any]:
        # Try Redis first (shared, authoritative)
        redis_val = redis_get(key)
        if redis_val is not None:
            return redis_val

        # Fall back to local (handles Redis-down and non-JSON-serializable values)
        return self._local_get(key)

    def _local_get(self, key: str) -> Optional[Any]:
        now = time.time()
        with self._lock:
            record = self._store.get(key)
            if record is None:
                return None
            expires_at, value = record
            if expires_at < now:
                del self._store[key]
                return None
            return value

    # ─────────────────────────────────────────────────────────────────
    # SET  — both Redis and local
    # ─────────────────────────────────────────────────────────────────

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = DEFAULT_TTL,
    ) -> None:
        # Write to Redis (fail-open — no-op on failure or non-JSON value)
        redis_set(key, value, ttl_seconds=ttl_seconds)
        # Always write to local as well (serves as fallback + process-local speed)
        self._local_set(key, value, ttl_seconds)

    def _local_set(self, key: str, value: Any, ttl_seconds: int) -> None:
        expires_at = time.time() + ttl_seconds
        with self._lock:
            if len(self._store) >= MAX_KEYS:
                self._evict_one()
            self._store[key] = (expires_at, value)

    # ─────────────────────────────────────────────────────────────────
    # DELETE  — both Redis and local
    # ─────────────────────────────────────────────────────────────────

    def delete(self, key: str) -> None:
        redis_delete(key)
        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        """Delete all keys starting with prefix. Returns count deleted from local store."""
        redis_delete_prefix(prefix)
        with self._lock:
            to_delete = [k for k in self._store if k.startswith(prefix)]
            for k in to_delete:
                del self._store[k]
            return len(to_delete)

    def delete_matching(self, predicate) -> int:
        """Delete all cache entries where predicate(key) is True. Returns count deleted."""
        # Redis: no efficient way to scan by arbitrary predicate — skip Redis here.
        # Use delete_prefix for prefix-based invalidation instead.
        with self._lock:
            to_delete = [k for k in self._store if predicate(k)]
            for k in to_delete:
                del self._store[k]
            return len(to_delete)

    # ─────────────────────────────────────────────────────────────────
    # CLEAR / SIZE  — local only (avoid flushing entire Redis DB)
    # ─────────────────────────────────────────────────────────────────

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)

    # ─────────────────────────────────────────────────────────────────
    # INTERNAL
    # ─────────────────────────────────────────────────────────────────

    def _evict_one(self) -> None:
        try:
            k = next(iter(self._store))
            del self._store[k]
        except StopIteration:
            return


response_cache = ResponseCache()
