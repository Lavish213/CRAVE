from __future__ import annotations

"""
olo_extractor.py
================
STATUS: NOT IMPLEMENTED

Olo is a white-label online ordering platform. No public API.
Extraction requires per-restaurant URL discovery and is not currently viable.
Returns empty list so provider_registry skips it gracefully.
"""

from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem


def extract_olo_menu(
    url: str,
    html: Optional[str] = None,
) -> List[ExtractedMenuItem]:
    """Olo menu extractor — NOT YET IMPLEMENTED. Returns [] gracefully."""
    return []
