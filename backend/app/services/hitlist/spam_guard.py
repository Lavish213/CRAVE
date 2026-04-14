# app/services/hitlist/spam_guard.py
from __future__ import annotations
import time
from collections import defaultdict, deque
from threading import RLock
from typing import Dict, Deque


class SpamGuard:
    def __init__(self) -> None:
        self._saves: Dict[str, Deque[float]] = defaultdict(deque)
        self._suggests: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = RLock()

    def allow_save(self, user_id: str, max_per_minute: int = 20) -> bool:
        return self._check(self._saves[user_id], max_per_minute)

    def allow_suggest(self, user_id: str, max_per_minute: int = 10) -> bool:
        return self._check(self._suggests[user_id], max_per_minute)

    def _check(self, window: Deque[float], limit: int) -> bool:
        now = time.time()
        cutoff = now - 60.0
        with self._lock:
            while window and window[0] < cutoff:
                window.popleft()
            if len(window) >= limit:
                return False
            window.append(now)
            return True


spam_guard = SpamGuard()
