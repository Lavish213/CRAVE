from __future__ import annotations

import logging
import threading
import time
from typing import Optional

import httpx


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# Global session state
# ---------------------------------------------------------

_client_lock = threading.Lock()
_http_client: Optional[httpx.Client] = None
_client_created_at: float = 0.0

# rotate session to avoid fingerprint / stale TLS reuse
SESSION_TTL_SECONDS = 300


# ---------------------------------------------------------
# Client creation
# ---------------------------------------------------------

def _create_client() -> httpx.Client:

    transport = httpx.HTTPTransport(
        retries=0,
    )

    limits = httpx.Limits(
        max_connections=100,
        max_keepalive_connections=20,
        keepalive_expiry=30,
    )

    client = httpx.Client(
        transport=transport,
        limits=limits,
        timeout=httpx.Timeout(
            connect=10.0,
            read=20.0,
            write=20.0,
            pool=10.0,
        ),
        follow_redirects=True,
        http2=True,  # 🔥 critical for modern sites
        headers={
            # baseline headers (can be overridden by fetcher)
            "Accept": "*/*",
            "Connection": "keep-alive",
        },
    )

    logger.debug("http_session_created")

    return client


# ---------------------------------------------------------
# TTL check
# ---------------------------------------------------------

def _is_expired() -> bool:
    if not _client_created_at:
        return False
    return (time.monotonic() - _client_created_at) > SESSION_TTL_SECONDS


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def get_session() -> httpx.Client:

    global _http_client, _client_created_at

    # fast path
    if _http_client and not _is_expired():
        return _http_client

    with _client_lock:

        if _http_client is None or _is_expired():

            if _http_client:
                try:
                    _http_client.close()
                except Exception:
                    pass

            _http_client = _create_client()
            _client_created_at = time.monotonic()

    return _http_client


# ---------------------------------------------------------
# Reset session (used on failures / blocks)
# ---------------------------------------------------------

def reset_session() -> None:

    global _http_client, _client_created_at

    with _client_lock:

        if _http_client:
            try:
                _http_client.close()
            except Exception:
                pass

        _http_client = None
        _client_created_at = 0.0

    logger.debug("http_session_reset")


# ---------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------

def close_session() -> None:

    global _http_client, _client_created_at

    with _client_lock:

        if _http_client:
            try:
                _http_client.close()
            except Exception as exc:
                logger.debug("session_close_error %s", exc)

        _http_client = None
        _client_created_at = 0.0

    logger.debug("http_session_closed")