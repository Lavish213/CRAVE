from __future__ import annotations

import time
import logging
import threading
from typing import Dict, Optional
from http.cookies import SimpleCookie
from urllib.parse import urlparse


logger = logging.getLogger(__name__)


MAX_DOMAINS = 5000
COOKIE_TTL = 86400


# ---------------------------------------------------------
# Thread safety
# ---------------------------------------------------------

_lock = threading.Lock()


class CookieJar:

    def __init__(self) -> None:
        self._store: Dict[str, Dict[str, dict]] = {}
        self._timestamps: Dict[str, float] = {}

    # ---------------------------------------------------------
    # Domain normalization
    # ---------------------------------------------------------

    def _normalize_domain(self, url: str) -> str:
        parsed = urlparse(url)
        domain = parsed.netloc.lower()

        if domain.startswith("www."):
            domain = domain[4:]

        return domain

    def _domain_variants(self, domain: str):
        parts = domain.split(".")
        variants = []

        for i in range(len(parts)):
            variants.append(".".join(parts[i:]))

        return variants

    # ---------------------------------------------------------
    # Cookie header builder
    # ---------------------------------------------------------

    def get_cookie_header(self, url: str) -> Optional[str]:

        domain = self._normalize_domain(url)
        variants = self._domain_variants(domain)

        now = time.time()
        cookies_out = {}

        with _lock:

            for variant in variants:

                cookies = self._store.get(variant)
                if not cookies:
                    continue

                for name, meta in cookies.items():

                    expires = meta.get("expires")

                    if expires and expires < now:
                        continue

                    cookies_out[name] = meta.get("value")

        if not cookies_out:
            return None

        return "; ".join(f"{k}={v}" for k, v in cookies_out.items())

    # ---------------------------------------------------------
    # Update cookies from response
    # ---------------------------------------------------------

    def update_from_response(self, url: str, headers) -> None:

        domain = self._normalize_domain(url)

        set_cookie_headers = []

        try:
            if hasattr(headers, "get_list"):
                set_cookie_headers = headers.get_list("set-cookie")
        except Exception:
            pass

        if not set_cookie_headers:
            for key, value in dict(headers).items():
                if key.lower() == "set-cookie":
                    set_cookie_headers.append(value)

        if not set_cookie_headers:
            return

        now = time.time()

        with _lock:

            for raw_cookie in set_cookie_headers:

                jar = SimpleCookie()

                try:
                    jar.load(raw_cookie)
                except Exception:
                    continue

                for key, morsel in jar.items():

                    try:
                        value = morsel.value
                        if not value:
                            continue

                        cookie_domain = morsel["domain"] or domain
                        cookie_domain = cookie_domain.lstrip(".").lower()

                        expires = None

                        # 🔥 proper expires handling
                        if morsel["max-age"]:
                            try:
                                expires = now + int(morsel["max-age"])
                            except Exception:
                                pass
                        elif morsel["expires"]:
                            # fallback: assign TTL if parse fails
                            expires = now + COOKIE_TTL

                        domain_store = self._store.setdefault(cookie_domain, {})

                        domain_store[key] = {
                            "value": value,
                            "expires": expires,
                        }

                        self._timestamps[cookie_domain] = now

                    except Exception:
                        continue

            self._cleanup()

    # ---------------------------------------------------------
    # Cleanup
    # ---------------------------------------------------------

    def _cleanup(self) -> None:

        if len(self._store) <= MAX_DOMAINS:
            return

        cutoff = time.time() - COOKIE_TTL

        to_delete = []

        for domain, ts in self._timestamps.items():
            if ts < cutoff:
                to_delete.append(domain)

        for domain in to_delete:
            self._store.pop(domain, None)
            self._timestamps.pop(domain, None)

        if len(self._store) > MAX_DOMAINS:

            sorted_domains = sorted(
                self._timestamps.items(),
                key=lambda x: x[1]
            )

            excess = len(self._store) - MAX_DOMAINS

            for domain, _ in sorted_domains[:excess]:
                self._store.pop(domain, None)
                self._timestamps.pop(domain, None)


# ---------------------------------------------------------
# Global instance
# ---------------------------------------------------------

_global_cookie_jar = CookieJar()


def get_cookie_header(url: str) -> Optional[str]:
    return _global_cookie_jar.get_cookie_header(url)


def update_cookies(url: str, headers) -> None:
    _global_cookie_jar.update_from_response(url, headers)