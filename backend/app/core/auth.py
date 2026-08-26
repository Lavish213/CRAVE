"""
API key authentication dependency.

Usage:
    from app.core.auth import require_api_key
    @router.post("/endpoint", dependencies=[Depends(require_api_key)])

Rules:
- Header: x-api-key
- Validated against API_KEY env var
- If env var is not set or empty, auth is bypassed (dev-friendly)
- Wrong key returns 401 {"detail": "Invalid API key"}
"""
from __future__ import annotations

import hmac
import logging
import os

from fastapi import Header, HTTPException
from typing import Optional

logger = logging.getLogger(__name__)


def require_api_key(x_api_key: Optional[str] = Header(default=None)) -> None:
    """
    FastAPI dependency that validates the x-api-key header.

    Bypass: if the API_KEY environment variable is not set or is empty,
    all requests are allowed regardless of whether a key is provided.
    This makes local development frictionless.
    """
    expected = os.environ.get("API_KEY", "").strip()

    # Dev-friendly bypass: if no key is configured, allow everything
    if not expected:
        logger.debug("auth_bypassed API_KEY not set — running in open mode")
        return

    if not hmac.compare_digest(x_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid API key")


def require_debug_api_key(x_debug_api_key: Optional[str] = Header(default=None)) -> None:
    """
    FastAPI dependency for the /debug router's sensitive introspection
    routes (raw recommendation-event row dumps, scheduler internals,
    EXPLAIN ANALYZE query plans against production data).

    Deliberately separate from require_api_key: API_KEY is sent as
    x-api-key on every request the mobile app makes, via
    EXPO_PUBLIC_API_KEY, which Expo compiles directly into the shipped
    JS bundle. Anyone with the app binary can extract it, so it proves a
    request came from *some* copy of the app, not that the caller is an
    operator. Gating admin-ish read access behind it was never a real
    authorization boundary.

    Unlike require_api_key, this fails closed: if DEBUG_API_KEY is not
    configured, every request is rejected — there is no dev-friendly
    open-mode bypass for raw data dumps and query-plan execution.
    DEBUG_API_KEY must be set only as a server-side env var (Railway),
    and must never be referenced by any EXPO_PUBLIC_* var, so it never
    ships to a client.
    """
    expected = os.environ.get("DEBUG_API_KEY", "").strip()

    if not expected:
        logger.warning("debug_api_key_not_configured — rejecting debug request")
        raise HTTPException(status_code=503, detail="Debug endpoints are not configured")

    if not hmac.compare_digest(x_debug_api_key or "", expected):
        raise HTTPException(status_code=401, detail="Invalid debug API key")
