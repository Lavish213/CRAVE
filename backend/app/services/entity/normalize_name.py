from __future__ import annotations

import re



# ---------------------------------------------------------
# REGEX
# ---------------------------------------------------------

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]")


# ---------------------------------------------------------
# ENTRYPOINT
# ---------------------------------------------------------

def normalize_name(name: str | None) -> str | None:
    """
    Normalize business name for matching.

    - lowercase
    - remove punctuation
    - collapse spaces
    """

    if not name:
        return None

    try:
        name = str(name).strip().lower()

        if not name:
            return None

        # remove punctuation
        name = _PUNCT_RE.sub("", name)

        # normalize spaces
        name = _SPACE_RE.sub(" ", name)

        return name.strip()

    except Exception:
        return None