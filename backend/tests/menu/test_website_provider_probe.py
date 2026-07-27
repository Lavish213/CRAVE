import pytest
from unittest.mock import patch, MagicMock
import httpx

from app.services.menu.discovery.website_provider_probe import (
    probe_website,
    ProbeResult,
    _score_url,
    _is_hard_blocked,
    _normalize_url,
    _normalize_website,
    MIN_SCORE,
)


def _mock_response(*, status_code=200, text="", url="https://example.com"):
    res = MagicMock(spec=httpx.Response)
    res.status_code = status_code
    res.text = text
    res.url = httpx.URL(url)
    return res


# ── Helper unit tests ─────────────────────────────────────────────────────────

def test_score_url_toast():
    assert _score_url("https://www.toasttab.com/horn-bbq") == (100, "toast")

def test_score_url_toast_homepage_rejected():
    # Marketing/homepage paths are excluded, not just any toasttab.com URL
    assert _score_url("https://www.toasttab.com") == (0, None)
    assert _score_url("https://www.toasttab.com/about") == (0, None)

def test_score_url_clover_is_hard_blocked_not_a_provider():
    # clover.com is a hard block (homepage only, no restaurant-specific path) —
    # it no longer scores as a valid provider.
    assert _score_url("https://clover.com/online-ordering/foo") == (0, None)

def test_score_url_popmenu():
    assert _score_url("https://order.popmenu.com/some-restaurant") == (90, "popmenu")

def test_score_url_popmenu_homepage_rejected():
    assert _score_url("https://popmenu.com/pricing") == (0, None)

def test_score_url_square_site():
    assert _score_url("https://some-place.square.site/order") == (80, "square")

def test_score_url_squareup_requires_store_path():
    assert _score_url("https://squareup.com/us/en") == (0, None)
    assert _score_url("https://squareup.com/store/some-place") == (80, "square")

def test_score_url_chownow():
    assert _score_url("https://www.chownow.com/order/some-place") == (70, "chownow")

def test_score_url_olo():
    assert _score_url("https://www.olo.com/order/some-place") == (60, "olo")

def test_score_url_unknown_domain():
    assert _score_url("https://hornbbq.com/menu") == (0, None)

def test_score_url_empty_string():
    assert _score_url("") == (0, None)


def test_is_hard_blocked_yelp():
    assert _is_hard_blocked("https://www.yelp.com/biz/place") is True

def test_is_hard_blocked_tripadvisor():
    assert _is_hard_blocked("https://tripadvisor.com/Restaurant_Review-foo") is True

def test_is_hard_blocked_clover():
    assert _is_hard_blocked("https://clover.com/online-ordering/foo") is True

def test_is_hard_blocked_real_site():
    assert _is_hard_blocked("https://hornbbq.com") is False


def test_normalize_url_adds_scheme():
    assert _normalize_url("hornbbq.com") == "https://hornbbq.com"

def test_normalize_url_strips_trailing_slash():
    assert _normalize_url("https://hornbbq.com/menu/") == "https://hornbbq.com/menu"

def test_normalize_url_strips_query_and_fragment():
    assert _normalize_url("https://hornbbq.com/menu?utm=1#top") == "https://hornbbq.com/menu"


def test_normalize_website_adds_scheme():
    assert _normalize_website("hornbbq.com") == "https://hornbbq.com"

def test_normalize_website_strips_trailing_slash():
    assert _normalize_website("https://hornbbq.com/") == "https://hornbbq.com"

def test_normalize_website_preserves_https():
    assert _normalize_website("https://hornbbq.com") == "https://hornbbq.com"


def test_probe_result_found_true_when_score_at_or_above_min():
    r = ProbeResult(menu_source_url="https://toasttab.com/foo", provider="toast", score=100, confidence=1.0)
    assert r.found is True

def test_probe_result_found_false_when_score_below_min():
    r = ProbeResult(menu_source_url="https://example.com/somepage", provider=None, score=20, confidence=0.2)
    assert r.found is False

def test_probe_result_found_false_when_no_url():
    r = ProbeResult(menu_source_url=None, provider=None, score=90, confidence=0.9)
    assert r.found is False


# ── probe_website integration tests (mocked fetch) ───────────────────────────

def test_probe_toast_redirect():
    """Direct redirect to toasttab.com → score=100, confidence=1.0, stops immediately"""
    res = _mock_response(
        url="https://www.toasttab.com/horn-barbecue/v3/menu",
        text="",
    )
    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://hornbbq.com")

    assert result.found is True
    assert result.provider == "toast"
    assert result.confidence == 1.0
    assert "toasttab.com" in result.menu_source_url


def test_probe_provider_link_in_html():
    """HTML contains a chownow.com link → score=70, confidence=0.7"""
    html = '<a href="https://www.chownow.com/order/some-place">Order</a>'
    res = _mock_response(text=html, url="https://example.com/menu")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "chownow"
    assert result.confidence == 0.7


def test_probe_jsonld_menu():
    """HTML contains JSON-LD Menu type, no provider link → score=40 (MIN_SCORE), confidence=0.4"""
    html = '<script type="application/ld+json">{"@type": "Menu"}</script>'
    res = _mock_response(text=html, url="https://example.com/menu")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "jsonld"
    assert result.confidence == 0.4


def test_probe_no_signals():
    """Plain HTML with no menu signals → not found"""
    html = "<html><body><p>Welcome!</p></body></html>"
    res = _mock_response(text=html, url="https://example.com")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is False
    assert result.confidence == 0.0


def test_probe_skips_aggregator_without_fetch():
    """Aggregator/hard-blocked domains skip all HTTP calls"""
    with patch("app.services.menu.discovery.website_provider_probe.fetch") as mock_fetch:
        result = probe_website("https://www.yelp.com/biz/some-place")

    mock_fetch.assert_not_called()
    assert result.found is False


def test_probe_prefers_redirect_over_html_link():
    """First path redirects straight to toast (score=100, the max) → early-stops
    before any HTML link scan even happens"""
    redirect_res = _mock_response(url="https://www.toasttab.com/foo")
    html_res = _mock_response(
        text='<a href="https://www.chownow.com/order/bar">Order</a>',
        url="https://example.com/menu",
    )
    with patch(
        "app.services.menu.discovery.website_provider_probe.fetch",
        side_effect=[redirect_res, html_res],
    ):
        result = probe_website("https://example.com")

    assert result.provider == "toast"
    assert result.confidence == 1.0


def test_probe_fetch_failure_returns_not_found():
    """Network failure on every path → not found, no exception propagates"""
    with patch(
        "app.services.menu.discovery.website_provider_probe.fetch",
        side_effect=Exception("connect timeout"),
    ):
        result = probe_website("https://hornbbq.com")

    assert result.found is False
    assert result.confidence == 0.0


def test_probe_non_200_status_continues_to_next_path():
    """404 on first path → tries next paths"""
    fail_res = _mock_response(status_code=404, text="", url="https://example.com")
    html_res = _mock_response(
        text='<a href="https://www.toasttab.com/some-place">Order</a>',
        url="https://example.com/menu",
    )
    plain = _mock_response(text="<html><body></body></html>", url="https://example.com/order")
    with patch(
        "app.services.menu.discovery.website_provider_probe.fetch",
        side_effect=[fail_res, html_res, plain, plain, plain, plain],
    ):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "toast"


def test_probe_html_provider_unknown_falls_through_to_jsonld():
    """When HTML has a provider URL that's hard-blocked (not a real provider),
    JSON-LD is still checked as a fallback"""
    # doordash.com is detected by discover_provider_urls's raw scan but is hard-
    # blocked in website_provider_probe, so it scores 0 and doesn't win.
    html = (
        '<a href="https://doordash.com/store/some-place">Order</a>'
        '<script type="application/ld+json">{"@type": "Menu"}</script>'
    )
    res = _mock_response(text=html, url="https://example.com/menu")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    # Should fall through to JSON-LD since doordash is hard-blocked, not scored
    assert result.found is True
    assert result.provider == "jsonld"
    assert result.confidence == 0.4
