from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


DEFAULT_MAX_ATTEMPTS = 3
DEFAULT_MAX_REDIRECTS = 5
DEFAULT_BACKOFF_SECONDS = 1.25


@dataclass(slots=True)
class RequestStrategy:
    mode: str
    referer: Optional[str]
    max_attempts: int
    max_redirects: int
    backoff_seconds: float
    warm_host_first: bool


def _safe_int(value: object, default: int) -> int:
    try:
        parsed = int(value)
        if parsed > 0:
            return parsed
    except Exception:
        pass
    return default


def _safe_float(value: object, default: float) -> float:
    try:
        parsed = float(value)
        if parsed > 0:
            return parsed
    except Exception:
        pass
    return default


def _policy_value(policy: object, key: str, default: object) -> object:
    if policy is None:
        return default

    if isinstance(policy, dict):
        return policy.get(key, default)

    return getattr(policy, key, default)


def _normalize_mode(mode: Optional[str]) -> str:
    value = (mode or "document").strip().lower()

    if value in {"document", "script", "api", "graphql"}:
        return value

    return "document"


def _infer_referer(
    *,
    url: str,
    explicit_referer: Optional[str],
    mode: str,
) -> Optional[str]:
    if explicit_referer:
        return explicit_referer

    if not url:
        return None

    if mode in {"document", "script", "api", "graphql"}:
        return url

    return None


def _adjust_mode_for_attempt(
    *,
    mode: str,
    attempt: int,
    previous_reason: Optional[str],
) -> str:
    reason = (previous_reason or "").lower()

    if attempt <= 1:
        return mode

    if mode in {"api", "graphql"}:
        return mode

    if reason in {"timeout", "server_error", "rate_limited"}:
        return mode

    if reason in {"empty", "empty_html", "empty_or_blocked_html"}:
        return mode

    if reason in {"redirect_trap", "auth_wall", "cloudflare_challenge", "captcha"}:
        return mode

    return mode


def _adjust_backoff(
    *,
    base_backoff: float,
    attempt: int,
    previous_reason: Optional[str],
) -> float:
    reason = (previous_reason or "").lower()
    value = base_backoff

    if reason in {"rate_limited", "soft_403", "hard_403"}:
        value = max(value, 2.0)

    if reason in {"server_error", "timeout"}:
        value = max(value, 1.5)

    if attempt > 1:
        value = value * attempt

    return min(value, 6.0)


def build_request_strategy(
    *,
    url: str,
    mode: str,
    method: str,
    referer: Optional[str],
    policy: object,
    attempt: int,
    previous_reason: Optional[str],
) -> RequestStrategy:
    normalized_mode = _normalize_mode(mode)

    adjusted_mode = _adjust_mode_for_attempt(
        mode=normalized_mode,
        attempt=attempt,
        previous_reason=previous_reason,
    )

    max_attempts = _safe_int(
        _policy_value(policy, "max_attempts", DEFAULT_MAX_ATTEMPTS),
        DEFAULT_MAX_ATTEMPTS,
    )

    max_redirects = _safe_int(
        _policy_value(policy, "max_redirects", DEFAULT_MAX_REDIRECTS),
        DEFAULT_MAX_REDIRECTS,
    )

    backoff_seconds = _safe_float(
        _policy_value(policy, "backoff_seconds", DEFAULT_BACKOFF_SECONDS),
        DEFAULT_BACKOFF_SECONDS,
    )

    warm_host_first = bool(
        _policy_value(policy, "warm_host_first", attempt == 1)
    )

    resolved_referer = _infer_referer(
        url=url,
        explicit_referer=referer,
        mode=adjusted_mode,
    )

    final_backoff = _adjust_backoff(
        base_backoff=backoff_seconds,
        attempt=attempt,
        previous_reason=previous_reason,
    )

    return RequestStrategy(
        mode=adjusted_mode,
        referer=resolved_referer,
        max_attempts=max_attempts,
        max_redirects=max_redirects,
        backoff_seconds=final_backoff,
        warm_host_first=warm_host_first,
    )