from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class ProxyPolicy:
    allow_proxy: bool
    force_proxy: bool
    proxy_after_attempt: int
    allow_browser_with_proxy: bool
    max_proxy_attempts: int


_DEFAULT = ProxyPolicy(
    allow_proxy=True,
    force_proxy=False,
    proxy_after_attempt=2,
    allow_browser_with_proxy=True,
    max_proxy_attempts=2,
)


STRICT_DOMAINS = {
    "toasttab.com",
    "chownow.com",
    "popmenu.com",
}


def get_proxy_policy(url: str) -> ProxyPolicy:
    url = (url or "").lower()

    for domain in STRICT_DOMAINS:
        if domain in url:
            return ProxyPolicy(
                allow_proxy=True,
                force_proxy=False,
                proxy_after_attempt=1,
                allow_browser_with_proxy=True,
                max_proxy_attempts=3,
            )

    return _DEFAULT