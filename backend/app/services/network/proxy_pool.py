from __future__ import annotations

import random
import time
from typing import Dict, Optional


_PROXIES = [
    # fill later
    # "http://user:pass@ip:port",
]


_COOLDOWN: Dict[str, float] = {}
_FAIL_COUNT: Dict[str, int] = {}


COOLDOWN_SECONDS = 60


def get_proxy() -> Optional[str]:
    candidates = []

    now = time.time()

    for proxy in _PROXIES:
        if proxy in _COOLDOWN and _COOLDOWN[proxy] > now:
            continue
        candidates.append(proxy)

    if not candidates:
        return None

    return random.choice(candidates)


def report_failure(proxy: str) -> None:
    _FAIL_COUNT[proxy] = _FAIL_COUNT.get(proxy, 0) + 1

    if _FAIL_COUNT[proxy] >= 2:
        _COOLDOWN[proxy] = time.time() + COOLDOWN_SECONDS


def report_success(proxy: str) -> None:
    _FAIL_COUNT[proxy] = 0
    _COOLDOWN.pop(proxy, None)