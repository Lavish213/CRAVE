"""
Coverage for app.services.images.website_image_extractor.WebsiteImageExtractor
-- previously untested. A production canary found zero free image
candidates on two real restaurant sites via this extractor; tracing the
code showed it only ever does a plain `requests.get()` + static HTML
parse, so any site that renders its photos client-side (Squarespace/Wix/
React, lazy-loaded galleries, CSS background-images) yields nothing --
not a data problem, a "this extractor can't see rendered content" problem.

These tests cover the two fixes: browser-escalation fallback (reusing the
same headless-renderer the menu pipeline already relies on) when static
extraction finds nothing, and lazy-load attribute support
(data-src/srcset) that helps even without escalating.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from app.services.images.website_image_extractor import WebsiteImageExtractor


def _place(**overrides):
    defaults = dict(id="place-1", website="https://restaurant.test", menu_source_url=None, grubhub_url=None)
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


STATIC_HTML_WITH_IMAGE = """
<html><head><meta property="og:image" content="/photos/interior-dining-room-wide-shot.jpg"></head>
<body><img src="/photos/signature-dish-full-resolution-photo.jpg"></body></html>
"""

STATIC_HTML_NO_IMAGES = "<html><head><title>Restaurant</title></head><body></body></html>"

LAZY_LOAD_HTML = """
<html><body>
<img data-src="/gallery/interior-shot-full-resolution-photo.jpg">
<img srcset="/gallery/plated-dish-photo-800px-wide.jpg 800w, /gallery/plated-dish-400px.jpg 400w">
</body></html>
"""

STRUCTURED_IMAGE_HTML = """
<html><head>
<meta property="og:image:secure_url" content="/hero.jpg">
<meta name="twitter:image:src" content="/social.jpg">
<link rel="image_src" href="/share.jpg">
<script type="application/ld+json">
{
  "@context": "https://schema.org",
  "@type": "Restaurant",
  "name": "Restaurant",
  "image": {"@type": "ImageObject", "contentUrl": "/food.jpg", "width": 1200, "height": 800},
  "photo": ["/room.jpg"],
  "logo": "/logo.jpg",
  "hasMenu": {
    "@type": "Menu",
    "hasMenuSection": [{"@type": "MenuSection", "image": "/dishes.jpg"}]
  }
}
</script>
</head><body>
<picture><source srcset="/plate-400.jpg 400w, /plate-1200.jpg 1200w"></picture>
<div style="background-image: url('/patio.jpg')"></div>
</body></html>
"""

RENDERED_HTML_WITH_IMAGE = """
<html><body><img src="https://cdn.restaurant.test/rendered-menu-photo-full-size.jpg"></body></html>
"""


def test_static_extraction_succeeds_without_ever_calling_browser_escalation():
    extractor = WebsiteImageExtractor()

    with (
        patch.object(extractor, "_fetch_html", return_value=STATIC_HTML_WITH_IMAGE),
        patch.object(extractor, "_fetch_html_via_browser") as mock_browser,
    ):
        results = extractor.extract(place=_place())

    mock_browser.assert_not_called()
    urls = {r["url"] for r in results}
    assert "https://restaurant.test/photos/interior-dining-room-wide-shot.jpg" in urls
    assert "https://restaurant.test/photos/signature-dish-full-resolution-photo.jpg" in urls


def test_escalates_to_browser_when_static_html_has_no_images():
    extractor = WebsiteImageExtractor()

    with (
        patch.object(extractor, "_fetch_html", return_value=STATIC_HTML_NO_IMAGES),
        patch.object(extractor, "_fetch_html_via_browser", return_value=RENDERED_HTML_WITH_IMAGE),
    ):
        results = extractor.extract(place=_place())

    urls = {r["url"] for r in results}
    assert "https://cdn.restaurant.test/rendered-menu-photo-full-size.jpg" in urls


def test_escalates_to_browser_when_the_static_fetch_itself_fails():
    """A hard block (403/captcha) on the plain GET is exactly the other
    documented browser-escalation trigger in browser_escalation.py --
    this extractor must reach for it too, not just on an empty parse."""
    extractor = WebsiteImageExtractor()

    with (
        patch.object(extractor, "_fetch_html", return_value=None),
        patch.object(extractor, "_fetch_html_via_browser", return_value=RENDERED_HTML_WITH_IMAGE),
    ):
        results = extractor.extract(place=_place())

    urls = {r["url"] for r in results}
    assert "https://cdn.restaurant.test/rendered-menu-photo-full-size.jpg" in urls


def test_returns_empty_when_both_static_and_browser_find_nothing():
    extractor = WebsiteImageExtractor()

    with (
        patch.object(extractor, "_fetch_html", return_value=STATIC_HTML_NO_IMAGES),
        patch.object(extractor, "_fetch_html_via_browser", return_value=None),
    ):
        results = extractor.extract(place=_place())

    assert results == []


def test_lazy_load_attributes_are_read_without_needing_escalation():
    extractor = WebsiteImageExtractor()

    with (
        patch.object(extractor, "_fetch_html", return_value=LAZY_LOAD_HTML),
        patch.object(extractor, "_fetch_html_via_browser") as mock_browser,
    ):
        results = extractor.extract(place=_place())

    mock_browser.assert_not_called()
    urls = {r["url"] for r in results}
    assert "https://restaurant.test/gallery/interior-shot-full-resolution-photo.jpg" in urls
    assert "https://restaurant.test/gallery/plated-dish-photo-800px-wide.jpg" in urls


def test_short_absolute_food_url_is_not_discarded_before_quality_scoring():
    extractor = WebsiteImageExtractor()

    results = extractor._extract_from_html(
        '<img src="https://r.test/a.jpg" alt="signature dish">',
        "https://r.test",
    )

    assert [result["url"] for result in results] == ["https://r.test/a.jpg"]


def test_extracts_authoritative_structured_and_responsive_image_sources():
    extractor = WebsiteImageExtractor()

    results = extractor._extract_from_html(STRUCTURED_IMAGE_HTML, "https://restaurant.test")

    by_url = {result["url"]: result for result in results}
    expected = {
        "https://restaurant.test/hero.jpg",
        "https://restaurant.test/social.jpg",
        "https://restaurant.test/share.jpg",
        "https://restaurant.test/food.jpg",
        "https://restaurant.test/room.jpg",
        "https://restaurant.test/dishes.jpg",
        "https://restaurant.test/plate-1200.jpg",
        "https://restaurant.test/patio.jpg",
    }
    assert expected <= set(by_url)
    assert "https://restaurant.test/logo.jpg" not in by_url
    assert by_url["https://restaurant.test/food.jpg"]["width"] == 1200
    assert by_url["https://restaurant.test/food.jpg"]["height"] == 800
