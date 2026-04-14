from __future__ import annotations

from typing import Any, Optional

from app.services.cache.response_cache import response_cache


def cache_get(key: str) -> Optional[Any]:
    return response_cache.get(key)


def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    response_cache.set(key, value, ttl_seconds=ttl_seconds)


def cache_delete(key: str) -> None:
    response_cache.delete(key)


def cache_clear() -> None:
    response_cache.clear()


def cache_size() -> int:
    return response_cache.size()
