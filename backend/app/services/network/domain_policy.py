from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DomainPolicy:
    max_attempts: int = 3
    max_redirects: int = 5
    backoff_seconds: float = 1.25
    warm_host_first: bool = True
    penalty_seconds: float = 12.0


_DEFAULT_POLICY = DomainPolicy()

_DOMAIN_POLICIES: dict[str, DomainPolicy] = {
    "grubhub.com": DomainPolicy(
        max_attempts=3,
        max_redirects=4,
        backoff_seconds=2.0,
        warm_host_first=True,
        penalty_seconds=20.0,
    ),
    "toasttab.com": DomainPolicy(
        max_attempts=2,
        max_redirects=4,
        backoff_seconds=2.0,
        warm_host_first=True,
        penalty_seconds=18.0,
    ),
    "order.online": DomainPolicy(
        max_attempts=2,
        max_redirects=4,
        backoff_seconds=2.0,
        warm_host_first=True,
        penalty_seconds=18.0,
    ),
    "chownow.com": DomainPolicy(
        max_attempts=2,
        max_redirects=4,
        backoff_seconds=1.5,
        warm_host_first=True,
        penalty_seconds=14.0,
    ),
    "popmenu.com": DomainPolicy(
        max_attempts=3,
        max_redirects=5,
        backoff_seconds=1.25,
        warm_host_first=True,
        penalty_seconds=10.0,
    ),
    "square.site": DomainPolicy(
        max_attempts=3,
        max_redirects=5,
        backoff_seconds=1.25,
        warm_host_first=True,
        penalty_seconds=10.0,
    ),
    "squareup.com": DomainPolicy(
        max_attempts=3,
        max_redirects=5,
        backoff_seconds=1.25,
        warm_host_first=True,
        penalty_seconds=10.0,
    ),
}


def get_domain_policy(url: str) -> DomainPolicy:
    lowered = (url or "").lower()

    for domain, policy in _DOMAIN_POLICIES.items():
        if domain in lowered:
            return policy

    return _DEFAULT_POLICY