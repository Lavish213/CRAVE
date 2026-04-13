from __future__ import annotations

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


# ---------------------------------------------------------
# Tracking params to strip
# ---------------------------------------------------------

TRACKING_PARAMS = {
    "ref",
    "fbclid",
    "gclid",
    "mc_cid",
    "mc_eid",
}


# ---------------------------------------------------------
# Normalize source URL
# ---------------------------------------------------------

def normalize_source_url(url: str | None) -> str:
    """
    Normalize menu source URLs so equivalent URLs collapse
    to a single canonical form before hashing.

    Guarantees:
    - consistent scheme
    - no tracking params
    - sorted query params
    - normalized host
    """

    if not url:
        return "unknown-source"

    try:
        parts = urlsplit(url.strip())
    except Exception:
        return "unknown-source"

    # ---------------- HOST ----------------
    host = (parts.netloc or "").lower()

    if host.startswith("www."):
        host = host[4:]

    if not host:
        return "unknown-source"

    # ---------------- QUERY ----------------
    query_pairs = [
        (k.lower(), v)
        for k, v in parse_qsl(parts.query, keep_blank_values=True)
        if not k.lower().startswith("utm_")
        and k.lower() not in TRACKING_PARAMS
    ]

    # 🔥 sort for determinism
    query = urlencode(sorted(query_pairs))

    # ---------------- PATH ----------------
    path = parts.path or "/"
    path = path.rstrip("/") or "/"

    # ---------------- SCHEME ----------------
    scheme = (parts.scheme or "https").lower()

    # ---------------- BUILD ----------------
    normalized = urlunsplit(
        (
            scheme,
            host,
            path,
            query,
            "",
        )
    )

    return normalized


# ---------------------------------------------------------
# Claim key builder
# ---------------------------------------------------------

def build_menu_claim_key(
    fingerprint: str,
    source_url: str | None,
) -> str:
    """
    Build claim key.

    fingerprint:
        Global identity of the item (NO PRICE)

    source_url:
        Source-specific identity

    Result:
        Unique per (item + source)

    Guarantees:
    - stable across runs
    - dedupe-safe
    - source-aware
    """

    if not fingerprint:
        raise ValueError("fingerprint required for menu claim")

    normalized_url = normalize_source_url(source_url)

    # 🔥 normalize fingerprint safety
    fingerprint = fingerprint.strip().lower()

    base = f"{fingerprint}|{normalized_url}"

    return hashlib.sha256(base.encode("utf-8")).hexdigest()