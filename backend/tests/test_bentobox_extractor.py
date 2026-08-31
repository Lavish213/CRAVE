from __future__ import annotations

from unittest.mock import patch

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.providers.bentobox_extractor import (
    _find_bentobox_pdf_url,
    extract_bentobox_menu,
)


# Real confirmed shape from docs/OVERTURE_ENTITY_REVIEW_2026-08-30.md's
# North Beach Sandwicheez source evidence, not a fabricated pattern.
_REAL_PDF_URL = (
    "https://media-cdn.getbento.com/accounts/29af413457a5fc32cec9f6558923fb90"
    "/media/IT33oRxIQI84aVWTERe3_fm1m4m6QTs2iD4AbH8Nf_xyaTef0uS4GO0i6RapDK"
    "_NBSandwicheez_PrintMenu.pdf"
)


def test_finds_bentobox_cdn_pdf_link_in_page_html():
    html = f'<html><body><a href="{_REAL_PDF_URL}">View Menu</a></body></html>'
    assert _find_bentobox_pdf_url(html) == _REAL_PDF_URL


def test_ignores_pdf_links_not_hosted_on_a_bentobox_cdn():
    html = '<html><body><a href="https://example.com/random-flyer.pdf">Flyer</a></body></html>'
    assert _find_bentobox_pdf_url(html) is None


def test_returns_none_for_missing_or_empty_html():
    assert _find_bentobox_pdf_url(None) is None
    assert _find_bentobox_pdf_url("") is None


def test_extract_bentobox_menu_delegates_to_pdf_extractor_when_link_found():
    html = f'<html><body><a href="{_REAL_PDF_URL}">Menu (PDF)</a></body></html>'
    fake_items = [ExtractedMenuItem(name="Turkey Club", price_cents=1195)]

    with patch(
        "app.services.menu.providers.bentobox_extractor.extract_pdf_menu",
        return_value=fake_items,
    ) as mock_pdf:
        result = extract_bentobox_menu("https://restaurant.test", html)

    mock_pdf.assert_called_once_with(_REAL_PDF_URL)
    assert result == fake_items


def test_extract_bentobox_menu_returns_empty_when_no_pdf_link_present():
    html = "<html><body>No menu here, just a JSON-LD page.</body></html>"
    with patch(
        "app.services.menu.providers.bentobox_extractor.extract_pdf_menu",
    ) as mock_pdf:
        result = extract_bentobox_menu("https://restaurant.test", html)

    mock_pdf.assert_not_called()
    assert result == []


def test_extract_bentobox_menu_swallows_pdf_extraction_errors():
    html = f'<html><body><a href="{_REAL_PDF_URL}">Menu</a></body></html>'
    with patch(
        "app.services.menu.providers.bentobox_extractor.extract_pdf_menu",
        side_effect=RuntimeError("download failed"),
    ):
        result = extract_bentobox_menu("https://restaurant.test", html)

    assert result == []
