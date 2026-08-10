"""
Coverage for menu_extraction_router.py's LLM-fallback wiring specifically
(not the full 7-strategy router, which has no prior test file at all).

Confirms the two things that matter about where extract_llm_menu was
plugged in: it's the true last resort (never called when a cheaper
strategy already found enough items), and it does get called — and its
result used — when every pattern-based strategy comes up empty against
real, non-empty HTML. That's exactly the fishgutscalifornia.com shape
this fallback exists for.

place_id is deliberately omitted (None) throughout — _write_snapshot no-ops
without one, so these tests don't touch the DB at all.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.menu_extraction_router import extract_menu

SAMPLE_HTML = "<html><body>Some restaurant page content</body></html>"


def _patch_all_heuristics_empty():
    """Context-manager stack patching every free strategy to find nothing,
    so only the LLM fallback (or browser escalation) can produce a result."""
    return (
        patch("app.services.menu.menu_extraction_router.detect_provider", return_value=None),
        patch("app.services.menu.menu_extraction_router.extract_hydration_menu", return_value=[]),
        patch("app.services.menu.menu_extraction_router.extract_jsonld_menu", return_value=[]),
        patch("app.services.menu.menu_extraction_router.extract_menu_from_js", return_value=[]),
        patch("app.services.menu.menu_extraction_router.discover_api_endpoints", return_value=[]),
        patch("app.services.menu.menu_extraction_router.extract_html_menu", return_value=[]),
        patch("app.services.menu.menu_extraction_router.detect_menu_iframes", return_value=[]),
        patch("app.services.menu.menu_extraction_router.rank_extraction_results", return_value=None),
    )


def test_llm_fallback_used_when_every_heuristic_finds_nothing():
    llm_items = [ExtractedMenuItem(name="Calamari", price_cents=1450, source_type="llm")]

    patches = _patch_all_heuristics_empty()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], \
         patch("app.services.menu.menu_extraction_router.extract_llm_menu", return_value=llm_items) as mock_llm, \
         patch("app.services.menu.menu_extraction_router.should_browser_escalate", return_value=False):
        result = extract_menu(SAMPLE_HTML, url="https://fishgutscalifornia.com", place_id=None)

    assert result == llm_items
    mock_llm.assert_called_once()


def test_llm_fallback_not_called_when_html_extractor_already_succeeds():
    """The exact scenario the fallback must NOT fire for — paying for an
    LLM call when a free strategy already found a good result would be
    pure waste."""
    good_html_items = [
        ExtractedMenuItem(name=f"Item {i}", price_cents=1000, source_type="html")
        for i in range(20)  # comfortably over HTML_FAST_RETURN_MIN
    ]

    with patch("app.services.menu.menu_extraction_router.detect_provider", return_value=None), \
         patch("app.services.menu.menu_extraction_router.extract_hydration_menu", return_value=[]), \
         patch("app.services.menu.menu_extraction_router.extract_jsonld_menu", return_value=[]), \
         patch("app.services.menu.menu_extraction_router.extract_menu_from_js", return_value=[]), \
         patch("app.services.menu.menu_extraction_router.discover_api_endpoints", return_value=[]), \
         patch("app.services.menu.menu_extraction_router.extract_html_menu", return_value=good_html_items), \
         patch("app.services.menu.menu_extraction_router.extract_llm_menu") as mock_llm:
        result = extract_menu(SAMPLE_HTML, url="https://example.test", place_id=None)

    assert len(result) == 20
    mock_llm.assert_not_called()


def test_llm_fallback_returns_final_fallback_when_llm_also_finds_nothing():
    patches = _patch_all_heuristics_empty()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], \
         patch("app.services.menu.menu_extraction_router.extract_llm_menu", return_value=[]), \
         patch("app.services.menu.menu_extraction_router.should_browser_escalate", return_value=False):
        result = extract_menu(SAMPLE_HTML, url="https://example.test", place_id=None)

    assert result == []


def test_llm_fallback_exception_does_not_crash_extraction():
    patches = _patch_all_heuristics_empty()
    with patches[0], patches[1], patches[2], patches[3], patches[4], patches[5], patches[6], patches[7], \
         patch(
             "app.services.menu.menu_extraction_router.extract_llm_menu",
             side_effect=RuntimeError("DeepSeek down"),
         ), \
         patch("app.services.menu.menu_extraction_router.should_browser_escalate", return_value=False):
        result = extract_menu(SAMPLE_HTML, url="https://example.test", place_id=None)

    assert result == []
