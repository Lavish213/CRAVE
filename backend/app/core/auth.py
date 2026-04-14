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
