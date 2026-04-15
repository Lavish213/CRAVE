import pytest
from unittest.mock import patch, MagicMock
import httpx

from app.services.menu.discovery.website_provider_probe import (
    probe_website,
    ProbeResult,
    _provider_from_url,
    _should_skip,
    _normalize_website,
    MIN_CONFIDENCE,
)


def _mock_response(*, status_code=200, text="", url="https://example.com"):
    res = MagicMock(spec=httpx.Response)
    res.status_code = status_code
    res.text = text
    res.url = httpx.URL(url)
    return res


# ── Helper unit tests ─────────────────────────────────────────────────────────

def test_provider_from_url_toast():
    assert _provider_from_url("https://www.toasttab.com/horn-bbq") == "toast"

def test_provider_from_url_clover():
    assert _provider_from_url("https://clover.com/online-ordering/foo") == "clover"

def test_provider_from_url_popmenu():
    assert _provider_from_url("https://order.popmenu.com/some-restaurant") == "popmenu"

def test_provider_from_url_square():
    assert _provider_from_url("https://some-place.square.site/order") == "square"

def test_provider_from_url_unknown():
    assert _provider_from_url("https://hornbbq.com/menu") is None

def test_should_skip_yelp():
    assert _should_skip("https://www.yelp.com/biz/place") is True

def test_should_skip_tripadvisor():
    assert _should_skip("https://tripadvisor.com/Restaurant_Review-foo") is True

def test_should_skip_real_site():
    assert _should_skip("https://hornbbq.com") is False

def test_normalize_adds_scheme():
    assert _normalize_website("hornbbq.com") == "https://hornbbq.com"

def test_normalize_strips_trailing_slash():
    assert _normalize_website("https://hornbbq.com/") == "https://hornbbq.com"

def test_normalize_preserves_https():
    assert _normalize_website("https://hornbbq.com") == "https://hornbbq.com"

def test_probe_result_found_true_when_high_confidence():
    r = ProbeResult(menu_source_url="https://toasttab.com/foo", provider="toast", confidence=1.0)
    assert r.found is True

def test_probe_result_found_false_when_low_confidence():
    r = ProbeResult(menu_source_url="https://example.com/menu", provider="jsonld", confidence=0.5)
    assert r.found is False

def test_probe_result_found_false_when_no_url():
    r = ProbeResult(menu_source_url=None, provider=None, confidence=0.9)
    assert r.found is False


# ── probe_website integration tests (mocked fetch) ───────────────────────────

def test_probe_toast_redirect():
    """Direct redirect to toasttab.com → confidence=1.0, stops immediately"""
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
    """HTML contains clover.com link → confidence=0.9"""
    html = '<a href="https://www.clover.com/online-ordering/some-place">Order</a>'
    res = _mock_response(text=html, url="https://example.com/menu")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "clover"
    assert result.confidence == 0.9


def test_probe_jsonld_menu():
    """HTML contains JSON-LD Menu type → confidence=0.7"""
    html = '<script type="application/ld+json">{"@type": "Menu"}</script>'
    res = _mock_response(text=html, url="https://example.com/menu")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "jsonld"
    assert result.confidence == 0.7


def test_probe_no_signals():
    """Plain HTML with no menu signals → not found"""
    html = "<html><body><p>Welcome!</p></body></html>"
    res = _mock_response(text=html, url="https://example.com")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    assert result.found is False
    assert result.confidence < MIN_CONFIDENCE


def test_probe_skips_aggregator_without_fetch():
    """Aggregator domains skip all HTTP calls"""
    with patch("app.services.menu.discovery.website_provider_probe.fetch") as mock_fetch:
        result = probe_website("https://www.yelp.com/biz/some-place")

    mock_fetch.assert_not_called()
    assert result.found is False


def test_probe_prefers_redirect_over_html_link():
    """First path redirects to provider → returns immediately at confidence=1.0"""
    redirect_res = _mock_response(url="https://www.toasttab.com/foo")
    html_res = _mock_response(
        text='<a href="https://clover.com/order/bar">Order</a>',
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
    """Network failure → not found, no exception propagates"""
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
    # html_res contains a toast link which causes `continue` after updating `best`
    # subsequent paths return plain HTML (no signals) until loop exhausts
    plain = _mock_response(text="<html><body></body></html>", url="https://example.com/order")
    with patch(
        "app.services.menu.discovery.website_provider_probe.fetch",
        side_effect=[fail_res, html_res, plain, plain, plain, plain],
    ):
        result = probe_website("https://example.com")

    assert result.found is True
    assert result.provider == "toast"


def test_probe_html_provider_unknown_falls_through_to_jsonld():
    """When HTML has a provider URL not in _PROVIDER_DOMAINS, JSON-LD is still checked"""
    # doordash.com is detected by discover_provider_urls but not in _PROVIDER_DOMAINS
    html = (
        '<a href="https://doordash.com/store/some-place">Order</a>'
        '<script type="application/ld+json">{"@type": "Menu"}</script>'
    )
    res = _mock_response(text=html, url="https://example.com/menu")

    with patch("app.services.menu.discovery.website_provider_probe.fetch", return_value=res):
        result = probe_website("https://example.com")

    # Should fall through to JSON-LD since doordash isn't in _PROVIDER_DOMAINS
    assert result.found is True
    assert result.provider == "jsonld"
    assert result.confidence == 0.7
