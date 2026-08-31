from __future__ import annotations

"""
bentobox_extractor.py
======================
BentoBox is a restaurant website CMS, not a POS/ordering API like Toast or
Square -- there is no generic JSON menu endpoint to call. What BentoBox
sites do commonly expose is a static PDF menu hosted on the platform's own
CDN (bentoboxcdn.com / getbento.com), linked from the page. Confirmed real
by production evidence, not a guess: the Oakland canary's North Beach
Sandwicheez entity review found exactly this shape --
media-cdn.getbento.com/accounts/.../NorthBeachSandwicheez_PrintMenu.pdf
(see docs/OVERTURE_ENTITY_REVIEW_2026-08-30.md).

This adapter only handles that one confirmed pattern: find a BentoBox-CDN
PDF link in the page HTML and hand it to the existing PDF extractor. It
does not attempt to parse BentoBox's page markup or any JSON state --
that would need live research against real BentoBox HTML this session
doesn't have access to. JSON-LD/hydration/HTML extraction already run
generically on BentoBox pages regardless of this adapter; this only adds
the PDF path those don't cover.
"""

import re
from typing import List, Optional

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.pdf_menu_extractor import extract_pdf_menu


_BENTOBOX_CDN_HOSTS = ("bentoboxcdn.com", "getbento.com")

_PDF_LINK_RE = re.compile(
    r"""href=["']([^"']+\.pdf[^"']*)["']""",
    re.IGNORECASE,
)


def _find_bentobox_pdf_url(html: Optional[str]) -> Optional[str]:
    if not html:
        return None

    for match in _PDF_LINK_RE.finditer(html):
        candidate = match.group(1)
        if any(host in candidate.lower() for host in _BENTOBOX_CDN_HOSTS):
            return candidate

    return None


def extract_bentobox_menu(
    url: str,
    html: Optional[str] = None,
) -> List[ExtractedMenuItem]:
    """Find a BentoBox-CDN-hosted PDF menu link in the page and extract it.

    Returns [] gracefully -- both when no such link exists (most BentoBox
    pages don't have one, or use JSON-LD/hydration instead, which already
    run independently of this adapter) and when the PDF is found but
    yields nothing.
    """
    pdf_url = _find_bentobox_pdf_url(html)
    if not pdf_url:
        return []

    try:
        return extract_pdf_menu(pdf_url)
    except Exception:
        return []
