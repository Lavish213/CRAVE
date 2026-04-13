from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(slots=True)
class SessionIdentity:
    id: str
    proxy: Optional[str]
    user_agent: str


_SESSIONS: Dict[str, SessionIdentity] = {}


DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)


def get_identity(host: str) -> SessionIdentity:
    if host in _SESSIONS:
        return _SESSIONS[host]

    identity = SessionIdentity(
        id=str(uuid.uuid4()),
        proxy=None,
        user_agent=DEFAULT_UA,
    )

    _SESSIONS[host] = identity
    return identity


def reset_identity(host: str) -> None:
    _SESSIONS.pop(host, None)