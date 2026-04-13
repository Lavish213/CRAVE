from __future__ import annotations

import hashlib
import random
import threading
import time
from typing import Dict


# ---------------------------------------------------------
# Browser profiles (REALISTIC FULL SETS)
# ---------------------------------------------------------

_BROWSER_PROFILES: tuple[dict[str, str], ...] = (
    {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="123", "Chromium";v="123", "Not:A-Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="122", "Chromium";v="122", "Not:A-Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
    },
    {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "sec-ch-ua": '"Google Chrome";v="121", "Chromium";v="121", "Not:A-Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Linux"',
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.7",
        "Accept-Encoding": "gzip, deflate, br",
        "Upgrade-Insecure-Requests": "1",
    },
)

# optional mobile (rare rotation)
_MOBILE_PROFILE = {
    "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile Safari/605.1",
    "sec-ch-ua-mobile": "?1",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


# ---------------------------------------------------------
# Config
# ---------------------------------------------------------

_WARM_TTL_SECONDS = 300
_MOBILE_PROBABILITY = 0.08  # 8% mobile traffic


# ---------------------------------------------------------
# State
# ---------------------------------------------------------

_LOCK = threading.RLock()
_HOST_PROFILE_INDEX: Dict[str, int] = {}
_LAST_WARM_TS: Dict[str, float] = {}


# ---------------------------------------------------------
# Header mutation (ANTI-FINGERPRINT)
# ---------------------------------------------------------

def _mutate_headers(headers: dict[str, str]) -> dict[str, str]:

    mutated = dict(headers)

    # small entropy in Accept-Language
    if "Accept-Language" in mutated:
        if random.random() < 0.3:
            mutated["Accept-Language"] = "en-US,en;q=0.8"

    # slight Accept variation
    if "Accept" in mutated and random.random() < 0.25:
        mutated["Accept"] = mutated["Accept"].replace("*/*", "*/*;q=0.9")

    return mutated


# ---------------------------------------------------------
# Sticky profile
# ---------------------------------------------------------

def get_sticky_profile(host: str) -> dict[str, str]:

    clean_host = (host or "unknown").lower()

    with _LOCK:

        if clean_host not in _HOST_PROFILE_INDEX:

            digest = hashlib.sha256(clean_host.encode("utf-8")).digest()
            index = digest[0] % len(_BROWSER_PROFILES)

            _HOST_PROFILE_INDEX[clean_host] = index

        index = _HOST_PROFILE_INDEX[clean_host]

        base = dict(_BROWSER_PROFILES[index])

        # occasional mobile spoof
        if random.random() < _MOBILE_PROBABILITY:
            base.update(_MOBILE_PROFILE)

        return _mutate_headers(base)


# ---------------------------------------------------------
# Warm logic
# ---------------------------------------------------------

def should_warm_host(host: str) -> bool:

    clean_host = (host or "unknown").lower()
    now = time.monotonic()

    with _LOCK:

        last = _LAST_WARM_TS.get(clean_host)

        if last is not None and (now - last) < _WARM_TTL_SECONDS:
            return False

        _LAST_WARM_TS[clean_host] = now
        return True