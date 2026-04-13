from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BrowserFingerprint:
    user_agent: str
    viewport: dict
    locale: str


DEFAULT_FINGERPRINT = BrowserFingerprint(
    user_agent=(
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    ),
    viewport={"width": 1280, "height": 800},
    locale="en-US",
)


def get_fingerprint() -> BrowserFingerprint:
    return DEFAULT_FINGERPRINT