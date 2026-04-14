# tests/social/test_platform_detect.py
import pytest
from app.services.social.platform_detect import detect_platform

@pytest.mark.parametrize("url,expected", [
    ("https://www.tiktok.com/@foodie/video/123", "tiktok"),
    ("https://vm.tiktok.com/ZMxyz/", "tiktok"),
    ("https://www.instagram.com/p/abc123/", "instagram"),
    ("https://www.youtube.com/watch?v=abc", "youtube"),
    ("https://youtu.be/abc", "youtube"),
    ("https://www.facebook.com/joespizza", "facebook"),
    ("https://fb.com/joespizza", "facebook"),
    ("https://maps.google.com/?q=...", "google_maps"),
    ("https://goo.gl/maps/abc", "google_maps"),
    ("https://www.yelp.com/biz/joes-pizza", "yelp"),
    ("https://www.grubhub.com/restaurant/...", "grubhub"),
    ("https://www.doordash.com/store/...", "doordash"),
    ("https://www.ubereats.com/store/...", "ubereats"),
    ("https://www.joespizza.com/menu", "generic"),
    (None, "unknown"),
    ("", "unknown"),
    ("not a url", "generic"),
])
def test_detect_platform(url, expected):
    assert detect_platform(url) == expected
