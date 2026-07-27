"""
Per-IP rate limiting dependency.

Sliding window (in-memory) or fixed window (Redis): 60 requests per 60-second
window, per IP address.

Usage:
    from app.core.rate_limit import rate_limit
    @router.get("/endpoint", dependencies=[Depends(rate_limit)])

IP resolution:
    1. X-Forwarded-For header (first entry) — only trusted when TRUSTED_PROXY
       is set, to prevent client IP spoofing.
    2. request.client.host — direct connection fallback

Backend selection:
    If REDIS_URL is set, uses a Redis-backed fixed-window counter shared
    across all worker processes/instances. Otherwise falls back to an
    in-memory sliding window that is per-process only — in a multi-worker
    deployment the effective limit becomes MAX_REQUESTS * num_workers. Set
    REDIS_URL in prod (Railway has a one-click Redis add-on) to close that gap.

Known limitation: keyed on IP, not on authenticated user. Multiple users
behind the same carrier NAT/office network share a bucket. Fixing this
properly requires running auth before rate limiting in the dependency chain;
left as a follow-up (see CRAVE_REMEDIATION_PLAN.md, Security section).
"""
from __future__ import annotations

import logging
import os
import time
from collections import deque
from threading import Lock
from typing import Deque, Dict, Optional

from fastapi import HTTPException, Request

from app.config.settings import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WINDOW_SECONDS: int = 60
MAX_REQUESTS: int = 60

# ---------------------------------------------------------------------------
# In-memory backend state
# ---------------------------------------------------------------------------

_buckets: Dict[str, Deque[float]] = {}
_lock = Lock()

# ---------------------------------------------------------------------------
# Redis backend (optional — shared across processes/instances)
# ---------------------------------------------------------------------------

_redis_client = None
if settings.redis_url:
    try:
        import redis as _redis_module

        _redis_client = _redis_module.from_url(
            settings.redis_url, decode_responses=True, socket_timeout=1.0
        )
        _redis_client.ping()
        logger.info("rate_limit_backend=redis")
    except Exception as exc:
        logger.warning(
            "rate_limit_redis_unavailable falling_back_to_memory error=%s", exc
        )
        _redis_client = None
else:
    logger.info(
        "rate_limit_backend=memory (set REDIS_URL for shared multi-worker limiting)"
    )


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def rate_limit(request: Request) -> None:
    """
    FastAPI dependency that enforces a per-IP rate limit.

    Raises HTTP 429 when the IP exceeds MAX_REQUESTS within WINDOW_SECONDS.
    """
    key = _get_ip(request)

    if _redis_client is not None:
        _redis_rate_limit(key)
    else:
        _memory_rate_limit(key)


def _redis_rate_limit(key: str) -> None:
    """Fixed-window counter shared across every worker/instance via Redis."""
    window = int(time.time()) // WINDOW_SECONDS
    redis_key = f"ratelimit:{key}:{window}"

    try:
        count = _redis_client.incr(redis_key)
        if count == 1:
            _redis_client.expire(redis_key, WINDOW_SECONDS)
    except Exception as exc:
        # Redis hiccup — fail open rather than taking the whole API down.
        logger.warning("rate_limit_redis_error key=%s error=%s", key, exc)
        return

    if count > MAX_REQUESTS:
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded. Try again later.",
        )


def _memory_rate_limit(key: str) -> None:
    """
    Sliding-window counter, single process only.

    Fixed from the original version: that implementation deleted and
    returned early on an empty bucket *without recording the current
    request*, so the first request in every fresh window (including the
    very first request from any client, and the first after any >=60s gap)
    was silently free and uncounted. This version always records the
    request that's being allowed through.
    """
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    with _lock:
        bucket = _buckets.setdefault(key, deque())

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= MAX_REQUESTS:
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded. Try again later.",
            )

        bucket.append(now)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_ip(request: Request) -> str:
    """
    Resolve client IP.

    Only trusts X-Forwarded-For when TRUSTED_PROXY env var is set to "1",
    "true", or "yes" — prevents clients from spoofing their IP via the header.
    Falls back to request.client.host, then "unknown".
    """
    if os.environ.get("TRUSTED_PROXY", "").lower() in ("1", "true", "yes"):
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
            if ip:
                return ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
