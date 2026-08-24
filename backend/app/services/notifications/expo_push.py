# app/services/notifications/expo_push.py
"""
Minimal client for Expo's push notification HTTP API
(https://exp.host/--/api/v2/push/send). Deliberately not the
`exponent-server-sdk` package -- the API here is one plain POST, and
avoiding the extra dependency keeps this consistent with how this app
already talks to other simple JSON APIs (see app/services/images/*.py's
own direct `requests` usage) rather than adding a client library for a
single endpoint.

Every function here is best-effort: a failed push is never something that
should affect the caller's own outcome (see video_processing_worker.py's
approve/reject paths, the only callers today) -- so nothing in this module
raises. Failures are logged and swallowed.
"""
from __future__ import annotations

import logging
from typing import Any, Iterable, Optional

import requests
from sqlalchemy.orm import Session

from app.db.models.device_push_token import DevicePushToken

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"
EXPO_PUSH_TIMEOUT_S = 10
# Expo's own documented cap on messages per request.
EXPO_PUSH_BATCH_SIZE = 100


def _chunks(items: list, size: int) -> Iterable[list]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def send_push_to_tokens(
    tokens: list[str],
    *,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
) -> None:
    if not tokens:
        return

    for batch in _chunks(tokens, EXPO_PUSH_BATCH_SIZE):
        messages = [
            {"to": token, "title": title, "body": body, "data": data or {}}
            for token in batch
        ]
        try:
            resp = requests.post(EXPO_PUSH_URL, json=messages, timeout=EXPO_PUSH_TIMEOUT_S)
            resp.raise_for_status()
            receipts = resp.json().get("data", [])
            for token, receipt in zip(batch, receipts):
                if receipt.get("status") != "ok":
                    logger.warning(
                        "expo_push_delivery_error token=%s error=%s",
                        token, receipt.get("message"),
                    )
        except Exception:
            logger.exception("expo_push_send_failed batch_size=%s", len(batch))


def send_push_to_user(
    db: Session,
    user_id: str,
    *,
    title: str,
    body: str,
    data: Optional[dict[str, Any]] = None,
) -> None:
    """Looks up every device registered for user_id and sends to all of them."""
    try:
        tokens = [
            row.push_token
            for row in db.query(DevicePushToken)
            .filter(DevicePushToken.user_id == user_id)
            .all()
        ]
    except Exception:
        logger.exception("expo_push_token_lookup_failed user_id=%s", user_id)
        return

    send_push_to_tokens(tokens, title=title, body=body, data=data)
