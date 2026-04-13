# FILE: backend/app/services/network/redirect_guard.py

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import urlparse


# ---------------------------------------------------------
# RESULT MODEL
# ---------------------------------------------------------

@dataclass(slots=True)
class RedirectDecision:
    allow: bool
    reason: str


# ---------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------

MAX_REDIRECTS = 5

_BLOCKED_DOMAINS = {
    "app.link",
    "branch.io",
    "onelink.me",
    "adjust.com",
}

_BLOCKED_PATH_KEYWORDS = {
    "download",
    "open-app",
    "app-download",
}

_LOOP_PROTECTION_HISTORY = 10


# ---------------------------------------------------------
# HELPERS
# ---------------------------------------------------------

def _safe_parse(url: str) -> Optional[str]:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return None


def _contains_blocked_path(url: str) -> bool:
    lowered = url.lower()
    return any(keyword in lowered for keyword in _BLOCKED_PATH_KEYWORDS)


def _is_blocked_domain(url: str) -> bool:
    host = _safe_parse(url)
    if not host:
        return False

    return any(blocked in host for blocked in _BLOCKED_DOMAINS)


def _is_loop(url: str, history: List[str]) -> bool:
    if not history:
        return False

    # simple loop detection
    if url in history[-_LOOP_PROTECTION_HISTORY:]:
        return True

    # domain-level loop
    current_host = _safe_parse(url)
    for prev in history[-_LOOP_PROTECTION_HISTORY:]:
        if _safe_parse(prev) == current_host:
            return True

    return False


# ---------------------------------------------------------
# MAIN DECISION
# ---------------------------------------------------------

def should_follow_redirect(
    *,
    next_url: str,
    redirect_count: int,
    history: List[str],
) -> RedirectDecision:

    # -----------------------------------------------------
    # MAX REDIRECT DEPTH
    # -----------------------------------------------------
    if redirect_count >= MAX_REDIRECTS:
        return RedirectDecision(
            allow=False,
            reason="max_redirects_exceeded",
        )

    # -----------------------------------------------------
    # LOOP DETECTION
    # -----------------------------------------------------
    if _is_loop(next_url, history):
        return RedirectDecision(
            allow=False,
            reason="redirect_loop_detected",
        )

    # -----------------------------------------------------
    # BLOCKED DOMAINS (app traps)
    # -----------------------------------------------------
    if _is_blocked_domain(next_url):
        return RedirectDecision(
            allow=False,
            reason="blocked_tracking_domain",
        )

    # -----------------------------------------------------
    # BLOCKED PATHS (app forcing)
    # -----------------------------------------------------
    if _contains_blocked_path(next_url):
        return RedirectDecision(
            allow=False,
            reason="blocked_app_redirect",
        )

    # -----------------------------------------------------
    # ALLOW
    # -----------------------------------------------------
    return RedirectDecision(
        allow=True,
        reason="ok",
    )


# ---------------------------------------------------------
# HISTORY MANAGEMENT
# ---------------------------------------------------------

def update_history(
    history: List[str],
    new_url: str,
) -> List[str]:
    if not new_url:
        return history

    history.append(new_url)

    # trim history
    if len(history) > _LOOP_PROTECTION_HISTORY:
        return history[-_LOOP_PROTECTION_HISTORY:]

    return history