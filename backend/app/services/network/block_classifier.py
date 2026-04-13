# FILE: backend/app/services/network/block_classifier.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# ---------------------------------------------------------
# RESULT MODEL
# ---------------------------------------------------------

@dataclass(slots=True)
class BlockClassification:
    is_blocked: bool
    reason: str

    retryable: bool
    penalize: bool

    escalate_to_browser: bool
    skip_same_strategy: bool


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

_HARD_403 = "hard_403"
_SOFT_403 = "soft_403"
_CLOUDFLARE = "cloudflare_challenge"
_CAPTCHA = "captcha"
_AUTH_WALL = "auth_wall"
_REDIRECT_TRAP = "redirect_trap"
_RATE_LIMIT = "rate_limited"
_TIMEOUT = "timeout"
_SERVER_ERROR = "server_error"
_EMPTY = "empty"
_OK = "ok"


# ---------------------------------------------------------
# MAIN CLASSIFIER
# ---------------------------------------------------------

def classify_response(
    *,
    status_code: Optional[int],
    text: Optional[str],
    final_url: Optional[str],
    redirect_count: int = 0,
) -> BlockClassification:

    body = (text or "").lower()
    url = (final_url or "").lower()

    # -----------------------------------------------------
    # REDIRECT TRAPS
    # -----------------------------------------------------
    if redirect_count >= 5:
        return BlockClassification(
            is_blocked=True,
            reason=_REDIRECT_TRAP,
            retryable=False,
            penalize=True,
            escalate_to_browser=False,
            skip_same_strategy=True,
        )

    if "app.link" in url or "download" in url:
        return BlockClassification(
            is_blocked=True,
            reason=_REDIRECT_TRAP,
            retryable=False,
            penalize=True,
            escalate_to_browser=False,
            skip_same_strategy=True,
        )

    # -----------------------------------------------------
    # HARDCODED BLOCK DETECTION (HTML SIGNALS)
    # -----------------------------------------------------
    if "cf-challenge" in body or "cloudflare" in body:
        return BlockClassification(
            is_blocked=True,
            reason=_CLOUDFLARE,
            retryable=False,
            penalize=True,
            escalate_to_browser=True,
            skip_same_strategy=True,
        )

    if "captcha" in body:
        return BlockClassification(
            is_blocked=True,
            reason=_CAPTCHA,
            retryable=False,
            penalize=True,
            escalate_to_browser=True,
            skip_same_strategy=True,
        )

    if "access denied" in body or "forbidden" in body:
        return BlockClassification(
            is_blocked=True,
            reason=_SOFT_403,
            retryable=False,
            penalize=True,
            escalate_to_browser=True,
            skip_same_strategy=True,
        )

    if "login" in body and "password" in body:
        return BlockClassification(
            is_blocked=True,
            reason=_AUTH_WALL,
            retryable=False,
            penalize=False,
            escalate_to_browser=False,
            skip_same_strategy=True,
        )

    # -----------------------------------------------------
    # STATUS-BASED CLASSIFICATION
    # -----------------------------------------------------
    if status_code == 403:
        return BlockClassification(
            is_blocked=True,
            reason=_HARD_403,
            retryable=False,
            penalize=True,
            escalate_to_browser=True,
            skip_same_strategy=True,
        )

    if status_code == 429:
        return BlockClassification(
            is_blocked=True,
            reason=_RATE_LIMIT,
            retryable=True,
            penalize=True,
            escalate_to_browser=False,
            skip_same_strategy=False,
        )

    if status_code and status_code >= 500:
        return BlockClassification(
            is_blocked=True,
            reason=_SERVER_ERROR,
            retryable=True,
            penalize=False,
            escalate_to_browser=False,
            skip_same_strategy=False,
        )

    # -----------------------------------------------------
    # EMPTY / JUNK RESPONSE
    # -----------------------------------------------------
    if not body or len(body) < 50:
        return BlockClassification(
            is_blocked=True,
            reason=_EMPTY,
            retryable=False,
            penalize=False,
            escalate_to_browser=False,
            skip_same_strategy=True,
        )

    # -----------------------------------------------------
    # SUCCESS
    # -----------------------------------------------------
    return BlockClassification(
        is_blocked=False,
        reason=_OK,
        retryable=False,
        penalize=False,
        escalate_to_browser=False,
        skip_same_strategy=False,
    )


# ---------------------------------------------------------
# EXCEPTION CLASSIFIER
# ---------------------------------------------------------

def classify_exception(exc: Exception) -> BlockClassification:
    msg = str(exc).lower()

    if "timeout" in msg:
        return BlockClassification(
            is_blocked=True,
            reason=_TIMEOUT,
            retryable=True,
            penalize=False,
            escalate_to_browser=False,
            skip_same_strategy=False,
        )

    if "403" in msg:
        return BlockClassification(
            is_blocked=True,
            reason=_HARD_403,
            retryable=False,
            penalize=True,
            escalate_to_browser=True,
            skip_same_strategy=True,
        )

    return BlockClassification(
        is_blocked=True,
        reason="unknown_error",
        retryable=False,
        penalize=False,
        escalate_to_browser=False,
        skip_same_strategy=False,
    )