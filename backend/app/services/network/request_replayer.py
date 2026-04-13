from __future__ import annotations

import logging
import time
from typing import Optional, Dict, Any

import httpx

from app.services.network.http_fetcher import fetch
from app.services.network.session_manager import reset_session
from app.services.menu.contracts import ReplayRequest, ReplayResponse


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# JSON detection
# ---------------------------------------------------------

def _safe_json(response: httpx.Response) -> Optional[Any]:

    try:
        return response.json()
    except Exception:
        return None


# ---------------------------------------------------------
# Core replay
# ---------------------------------------------------------

def replay_request(
    request: ReplayRequest,
    *,
    timeout: Optional[float] = None,
) -> ReplayResponse:

    start = time.monotonic()

    try:

        response = fetch(
            request.url,
            method=request.method,
            headers=request.headers or {},
            json=request.payload if isinstance(request.payload, dict) else None,
            data=request.payload if not isinstance(request.payload, dict) else None,
            timeout=timeout,
            referer=request.url,  # 🔥 critical anti-bot signal
        )

        # ---------------------------------------------------------
        # Retry on soft blocks
        # ---------------------------------------------------------

        if response.status_code in (403, 429):
            logger.debug(
                "replay_retry_blocked method=%s url=%s status=%s",
                request.method,
                request.url,
                response.status_code,
            )

            reset_session()

            response = fetch(
                request.url,
                method=request.method,
                headers=request.headers or {},
                json=request.payload if isinstance(request.payload, dict) else None,
                data=request.payload if not isinstance(request.payload, dict) else None,
                timeout=timeout,
                referer=request.url,
            )

        latency = round(time.monotonic() - start, 3)

        json_body = _safe_json(response)

        logger.debug(
            "replay_success method=%s url=%s status=%s latency=%ss json=%s",
            request.method,
            request.url,
            response.status_code,
            latency,
            bool(json_body),
        )

        return ReplayResponse(
            status_code=response.status_code,
            body=response.text if not json_body else None,
            json=json_body,
            headers=dict(response.headers),
        )

    except Exception as exc:

        latency = round(time.monotonic() - start, 3)

        logger.debug(
            "replay_failed method=%s url=%s latency=%ss error=%s",
            request.method,
            request.url,
            latency,
            exc,
        )

        raise


# ---------------------------------------------------------
# Endpoint validation helper
# ---------------------------------------------------------

def validate_endpoint(
    url: str,
    *,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    payload: Optional[Any] = None,
) -> bool:

    try:

        response = replay_request(
            ReplayRequest(
                url=url,
                method=method,
                headers=headers or {},
                payload=payload,
            )
        )

        if response.status_code >= 400:
            return False

        if response.json and isinstance(response.json, (dict, list)):
            return True

        if response.body and len(response.body.strip()) > 0:
            return True

        return False

    except Exception:
        return False


# ---------------------------------------------------------
# GraphQL replay helper
# ---------------------------------------------------------

def replay_graphql(
    endpoint: str,
    *,
    query: Optional[str] = None,
    variables: Optional[Dict[str, Any]] = None,
    operation_name: Optional[str] = None,
    persisted_hash: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None,
) -> ReplayResponse:

    payload: Dict[str, Any] = {}

    if query:
        payload["query"] = query

    if variables:
        payload["variables"] = variables

    if operation_name:
        payload["operationName"] = operation_name

    if persisted_hash:
        payload["extensions"] = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": persisted_hash,
            }
        }

    request = ReplayRequest(
        url=endpoint,
        method="POST",
        headers=headers or {},
        payload=payload,
    )

    return replay_request(request)