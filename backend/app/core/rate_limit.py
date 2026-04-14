"""
Per-IP rate limiting dependency (in-memory, no Redis).

Sliding window: 60 requests per 60-second window, per IP address.

Usage:
    from app.core.rate_limit import rate_limit
    @router.get("/endpoint", dependencies=[Depends(rate_limit)])

IP resolution:
    1. X-Forwarded-For header (first entry) — for reverse proxy deployments
    2. request.client.host — direct connection fallback
"""
from __future__ import annotations

import os
import time
from collections import deque
from threading import Lock
from typing import Deque, Dict

from fastapi import HTTPException, Request


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WINDOW_SECONDS: int = 60
MAX_REQUESTS: int = 60

# ---------------------------------------------------------------------------
# State (module-level singleton)
# NOTE: This limiter works across threads in a single process. In multi-process
# deployments (e.g. Gunicorn with multiple workers), each worker has its own
# in-memory state, so the effective limit is MAX_REQUESTS * num_workers.
# For multi-process deployments, use a Redis-backed limiter instead.
# ---------------------------------------------------------------------------

_buckets: Dict[str, Deque[float]] = {}
_lock = Lock()


# ---------------------------------------------------------------------------
# Dependency
# ---------------------------------------------------------------------------

def rate_limit(request: Request) -> None:
    """
    FastAPI dependency that enforces a per-IP sliding-window rate limit.

    Raises HTTP 429 when the IP exceeds MAX_REQUESTS within WINDOW_SECONDS.
    """
    ip = _get_ip(request)
    now = time.time()
    cutoff = now - WINDOW_SECONDS

    with _lock:
        if ip not in _buckets:
            _buckets[ip] = deque()

        bucket: Deque[float] = _buckets[ip]

        # Evict timestamps outside the current window
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if not bucket:
            del _buckets[ip]
            return  # bucket was empty, so this request is fine — let it through

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
    # Only trust X-Forwarded-For when running behind a verified proxy
    if os.environ.get("TRUSTED_PROXY", "").lower() in ("1", "true", "yes"):
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            ip = forwarded_for.split(",")[0].strip()
            if ip:
                return ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"
