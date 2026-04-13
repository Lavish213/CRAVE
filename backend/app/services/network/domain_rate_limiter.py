from __future__ import annotations

import logging
import random
import threading
import time
from typing import Dict
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


# ---------------------------------------------------------
# State
# ---------------------------------------------------------

_domain_last_request: Dict[str, float] = {}
_domain_penalty_until: Dict[str, float] = {}
_domain_penalty_level: Dict[str, int] = {}

_domain_lock = threading.Lock()


# ---------------------------------------------------------
# Config
# ---------------------------------------------------------

_DEFAULT_DELAY = 2.0
_MAX_DOMAIN_TRACK = 20000
_DOMAIN_MEMORY_TTL = 3600

_MAX_PENALTY_LEVEL = 4

# jitter range (adaptive)
_JITTER_MIN = 0.04
_JITTER_MAX = 0.22


# ---------------------------------------------------------
# Known domain speed rules
# ---------------------------------------------------------

_DOMAIN_RULES = {

    # menu providers
    "toasttab.com": 1.0,
    "squareup.com": 1.0,
    "square.site": 1.0,
    "olo.com": 1.0,
    "chownow.com": 1.0,

    # aggregators
    "doordash.com": 1.0,
    "ubereats.com": 1.0,
    "grubhub.com": 1.0,

    # CDN fast lanes
    "cloudfront.net": 0.6,
    "amazonaws.com": 0.6,

    # generic CDN hint
    "cdn": 0.5,
}


# ---------------------------------------------------------
# Domain parsing
# ---------------------------------------------------------

def _normalize_domain(domain: str) -> str:

    domain = domain.lower().strip()

    if domain.startswith("www."):
        domain = domain[4:]

    parts = domain.split(".")

    # safer extraction (handles co.uk, etc.)
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net"}:
        return ".".join(parts[-3:])

    if len(parts) >= 2:
        return ".".join(parts[-2:])

    return domain


def _extract_domain(url: str) -> str:

    try:
        parsed = urlparse(url)
        return _normalize_domain(parsed.netloc)
    except Exception:
        return "unknown"


# ---------------------------------------------------------
# Delay logic
# ---------------------------------------------------------

def _get_base_delay(domain: str) -> float:

    for rule_domain, delay in _DOMAIN_RULES.items():
        if domain.endswith(rule_domain):
            return delay

    return _DEFAULT_DELAY


def _get_penalty_delay(domain: str) -> float:

    penalty_until = _domain_penalty_until.get(domain)

    if not penalty_until:
        return 0.0

    now = time.monotonic()

    if now > penalty_until:
        _domain_penalty_until.pop(domain, None)
        _domain_penalty_level.pop(domain, None)
        return 0.0

    level = _domain_penalty_level.get(domain, 1)

    # exponential-ish scaling
    return 1.2 * (level ** 1.4)


# ---------------------------------------------------------
# Penalty system
# ---------------------------------------------------------

def penalize_domain(url: str, seconds: float = 20.0) -> None:

    domain = _extract_domain(url)

    with _domain_lock:

        now = time.monotonic()

        level = _domain_penalty_level.get(domain, 0)
        level = min(level + 1, _MAX_PENALTY_LEVEL)

        _domain_penalty_level[domain] = level

        duration = seconds * (1 + (level * 0.8))

        _domain_penalty_until[domain] = now + duration

        logger.debug(
            "domain_penalized domain=%s level=%s duration=%s",
            domain,
            level,
            round(duration, 2),
        )


# ---------------------------------------------------------
# Cleanup
# ---------------------------------------------------------

def _cleanup_domains() -> None:

    if len(_domain_last_request) <= _MAX_DOMAIN_TRACK:
        return

    cutoff = time.monotonic() - _DOMAIN_MEMORY_TTL

    keys = list(_domain_last_request.keys())

    for key in keys:

        ts = _domain_last_request.get(key)

        if ts and ts < cutoff:

            _domain_last_request.pop(key, None)
            _domain_penalty_until.pop(key, None)
            _domain_penalty_level.pop(key, None)


# ---------------------------------------------------------
# Public API
# ---------------------------------------------------------

def wait_for_domain(url: str) -> None:
    """
    Smart per-domain rate limiter with:
    - adaptive delay
    - penalty system
    - jitter
    - thread safety
    """

    domain = _extract_domain(url)

    base_delay = _get_base_delay(domain)
    penalty_delay = _get_penalty_delay(domain)

    total_delay = base_delay + penalty_delay

    now = time.monotonic()
    sleep_time = 0.0

    with _domain_lock:

        last_time = _domain_last_request.get(domain)

        if last_time is not None:

            elapsed = now - last_time
            remaining = total_delay - elapsed

            if remaining > 0:
                sleep_time = remaining

        # 🔥 reserve slot immediately (prevents thundering herd)
        _domain_last_request[domain] = now

        _cleanup_domains()

    # ---------------------------------------------------------
    # Sleep outside lock
    # ---------------------------------------------------------

    if sleep_time > 0:

        jitter = random.uniform(_JITTER_MIN, _JITTER_MAX)

        time.sleep(sleep_time + jitter)