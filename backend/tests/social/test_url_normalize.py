# tests/social/test_url_normalize.py
import pytest
from app.services.social.url_normalize import normalize_url

def test_strips_utm_params():
    url = "https://www.tiktok.com/@user/video/123?utm_source=copy&utm_medium=android"
    result = normalize_url(url)
    assert "utm_source" not in result
    assert "utm_medium" not in result
    assert "@user/video/123" in result

def test_strips_fbclid():
    url = "https://www.facebook.com/foo?fbclid=IwAbc123"
    result = normalize_url(url)
    assert "fbclid" not in result

def test_strips_igshid():
    url = "https://www.instagram.com/p/abc/?igshid=xyz"
    result = normalize_url(url)
    assert "igshid" not in result

def test_lowercases_host():
    url = "https://WWW.TIKTOK.COM/@user/video/123"
    result = normalize_url(url)
    assert "www.tiktok.com" in result

def test_removes_trailing_slash():
    url = "https://www.tiktok.com/@user/"
    result = normalize_url(url)
    assert result.endswith("@user")

def test_none_returns_none():
    assert normalize_url(None) is None

def test_empty_returns_none():
    assert normalize_url("") is None

def test_preserves_non_tracking_params():
    url = "https://example.com/menu?category=pizza&size=large"
    result = normalize_url(url)
    assert "category=pizza" in result
    assert "size=large" in result
