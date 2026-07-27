"""
Redis client — lazy connect, circuit breaker, fail-open.

Contract:
- redis_get  → None on miss OR any failure
- redis_set  → silent no-op on failure
- redis_delete → silent no-op on failure
- redis_delete_prefix → 0 on failure
- Redis unavailable → all operations fall through silently
- No exception ever escapes this module to callers

Circuit breaker:
- After any failure: 30s backoff before next attempt
- After successful call: circuit resets
- No Redis URL configured: permanently disabled (no retries)

Serialization: JSON only — all cached values must be JSON-serializable.
If json.dumps fails, the set is a no-op and caller falls back to in-memory.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


_BACKOFF_SECONDS = 30.0
_CONNECT_TIMEOUT = 1.0   # socket connect timeout
_SOCKET_TIMEOUT = 1.0    # per-operation timeout

_client = None           # redis.Redis instance once connected
_fail_until: float = 0.0 # monotonic time before which we skip Redis
_no_url: bool = False    # True if REDIS_URL is empty — never retry


def _try_connect() -> Optional[Any]:
    """
    Attempt to create and ping Redis client.
    Returns the client or None. Sets _fail_until on failure.
    """
    global _client, _fail_until, _no_url

    try:
        from app.config.settings import settings
        url = (settings.redis_url or "").strip()
    except Exception:
        _no_url = True
        return None

    if not url:
        _no_url = True
        return None

    redis_mod = _import_redis()
    if redis_mod is None:
        _no_url = True
        return None

    try:
        c = redis_mod.Redis.from_url(
            url,
            socket_connect_timeout=_CONNECT_TIMEOUT,
            socket_timeout=_SOCKET_TIMEOUT,
            decode_responses=True,   # strings in, strings out — JSON-safe
        )
        c.ping()
        _client = c
        logger.info("redis_connected url=%s", url)
        return _client

    except Exception as exc:
        _fail_until = time.monotonic() + _BACKOFF_SECONDS
        logger.warning("redis_connect_failed error=%s backoff=%ss", exc, _BACKOFF_SECONDS)
        return None


def _import_redis() -> Optional[Any]:
    try:
        import redis as _r
        return _r
    except ImportError:
        logger.debug("redis_package_not_installed — in-memory cache only")
        return None


def _get() -> Optional[Any]:
    """
    Return the active Redis client, or None if unavailable.
    Handles lazy connect, circuit breaker, and reconnect after backoff.
    """
    global _client, _fail_until, _no_url

    if _no_url:
        return None

    now = time.monotonic()
    if now < _fail_until:
        return None

    if _client is not None:
        return _client

    return _try_connect()


def _mark_failure(exc: Exception, op: str, key: str = "") -> None:
    global _client, _fail_until
    logger.debug("redis_%s_failed key=%s error=%s", op, key, exc)
    _fail_until = time.monotonic() + _BACKOFF_SECONDS
    _client = None  # force reconnect on next attempt after backoff


def _encode(value: Any) -> Optional[str]:
    """Encode value as JSON string. Returns None if not serializable."""
    try:
        return json.dumps(value, separators=(",", ":"), ensure_ascii=False)
    except (TypeError, ValueError):
        return None


def _decode(raw: str) -> Optional[Any]:
    """Decode JSON string. Returns None on failure."""
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def redis_get(key: str) -> Optional[Any]:
    r = _get()
    if r is None:
        return None
    try:
        raw = r.get(key)
        if raw is None:
            return None
        return _decode(raw)
    except Exception as exc:
        _mark_failure(exc, "get", key)
        return None


def redis_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    r = _get()
    if r is None:
        return
    encoded = _encode(value)
    if encoded is None:
        return  # not JSON-serializable — skip Redis, caller uses in-memory
    try:
        r.setex(key, max(1, ttl_seconds), encoded)
    except Exception as exc:
        _mark_failure(exc, "set", key)


def redis_delete(key: str) -> None:
    r = _get()
    if r is None:
        return
    try:
        r.delete(key)
    except Exception as exc:
        _mark_failure(exc, "delete", key)


def redis_delete_prefix(prefix: str) -> int:
    """
    Delete all keys with given prefix using SCAN (safe for large key spaces).
    Returns count of deleted keys, or 0 on failure.
    """
    r = _get()
    if r is None:
        return 0
    try:
        deleted = 0
        cursor = 0
        pattern = f"{prefix}*"
        while True:
            cursor, keys = r.scan(cursor, match=pattern, count=200)
            if keys:
                r.delete(*keys)
                deleted += len(keys)
            if cursor == 0:
                break
        return deleted
    except Exception as exc:
        _mark_failure(exc, "delete_prefix", prefix)
        return 0


def redis_available() -> bool:
    """Return True if Redis is currently reachable."""
    return _get() is not None
