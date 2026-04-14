from __future__ import annotations

import time
from threading import RLock
from typing import Any, Optional, Dict, Tuple


DEFAULT_TTL = 60
MAX_KEYS = 50_000


class ResponseCache:

    def __init__(self) -> None:
        self._store: Dict[str, Tuple[float, Any]] = {}
        self._lock = RLock()

    def get(self, key: str) -> Optional[Any]:

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

    def set(
        self,
        key: str,
        value: Any,
        ttl_seconds: int = DEFAULT_TTL,
    ) -> None:

        expires_at = time.time() + ttl_seconds

        with self._lock:

            if len(self._store) >= MAX_KEYS:
                self._evict_one()

            self._store[key] = (expires_at, value)

    def _evict_one(self) -> None:

        try:
            k = next(iter(self._store))
            del self._store[k]
        except StopIteration:
            return

    def delete(self, key: str) -> None:

        with self._lock:
            self._store.pop(key, None)

    def delete_prefix(self, prefix: str) -> int:
        """Delete all keys starting with prefix. Returns count deleted."""
        with self._lock:
            to_delete = [k for k in self._store if k.startswith(prefix)]
            for k in to_delete:
                del self._store[k]
            return len(to_delete)

    def clear(self) -> None:

        with self._lock:
            self._store.clear()

    def size(self) -> int:

        with self._lock:
            return len(self._store)


response_cache = ResponseCache()