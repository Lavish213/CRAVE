from __future__ import annotations

import re


# ---------------------------------------------------------
# REGEX
# ---------------------------------------------------------

_SPACE_RE = re.compile(r"\s+")


# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------

def normalize_address(address: str | None) -> str | None:
    """
    Normalize address string for matching.

    - lowercase
    - trims spaces
    - collapses whitespace
    """

    if not address:
        return None

    try:
        address = str(address).lower().strip()

        if not address:
            return None

        address = _SPACE_RE.sub(" ", address)

        return address

    except Exception:
        return None