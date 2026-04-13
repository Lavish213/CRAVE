# FILE: backend/app/services/network/stealth_headers.py

from __future__ import annotations

import random
from typing import Dict, Optional


# ---------------------------------------------------------
# USER AGENTS (REALISTIC POOL)
# ---------------------------------------------------------

USER_AGENTS = [
    # Chrome Mac
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",

    # Chrome Windows
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",

    # Chrome Linux
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36",
]


# ---------------------------------------------------------
# ACCEPT HEADERS (VARIANTS)
# ---------------------------------------------------------

ACCEPT_HEADERS = [
    "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "text/html,application/xml;q=0.9,*/*;q=0.8",
]


# ---------------------------------------------------------
# LANGUAGE OPTIONS
# ---------------------------------------------------------

LANG_HEADERS = [
    "en-US,en;q=0.9",
    "en-US,en;q=0.8",
]


# ---------------------------------------------------------
# BUILD HEADERS
# ---------------------------------------------------------

def build_stealth_headers(
    *,
    url: Optional[str] = None,
    referer: Optional[str] = None,
    is_api: bool = False,
) -> Dict[str, str]:

    headers: Dict[str, str] = {}

    # -----------------------------------------------------
    # CORE BROWSER IDENTITY
    # -----------------------------------------------------
    headers["User-Agent"] = random.choice(USER_AGENTS)
    headers["Accept"] = random.choice(ACCEPT_HEADERS)
    headers["Accept-Language"] = random.choice(LANG_HEADERS)
    headers["Accept-Encoding"] = "gzip, deflate, br"

    # -----------------------------------------------------
    # CONNECTION / PRIORITY
    # -----------------------------------------------------
    headers["Connection"] = "keep-alive"
    headers["Upgrade-Insecure-Requests"] = "1"

    # -----------------------------------------------------
    # REFERER LOGIC (VERY IMPORTANT)
    # -----------------------------------------------------
    if referer:
        headers["Referer"] = referer
    elif url:
        headers["Referer"] = _infer_referer(url)

    # -----------------------------------------------------
    # SEC-FETCH HEADERS (CRITICAL FOR ANTI-BOT)
    # -----------------------------------------------------
    headers["Sec-Fetch-Dest"] = "document"
    headers["Sec-Fetch-Mode"] = "navigate"
    headers["Sec-Fetch-Site"] = "none"
    headers["Sec-Fetch-User"] = "?1"

    # -----------------------------------------------------
    # CACHE BEHAVIOR
    # -----------------------------------------------------
    headers["Cache-Control"] = "max-age=0"

    # -----------------------------------------------------
    # API MODE ADJUSTMENTS
    # -----------------------------------------------------
    if is_api:
        headers["Accept"] = "application/json, text/plain, */*"
        headers["Sec-Fetch-Mode"] = "cors"
        headers["Sec-Fetch-Dest"] = "empty"
        headers["Sec-Fetch-Site"] = "same-origin"

    return headers


# ---------------------------------------------------------
# REFERER INFERENCE
# ---------------------------------------------------------

def _infer_referer(url: str) -> str:
    try:
        from urllib.parse import urlparse

        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        return base
    except Exception:
        return ""