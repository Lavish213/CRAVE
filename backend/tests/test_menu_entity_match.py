"""
Coverage for app.services.menu.extraction.entity_match -- the guard added
after a production contamination incident where a restaurant's menu
extraction pulled in a second, unrelated vendor's items ("Hopscotch")
through a shared iframe/API widget embedded on the target's own page.
Nothing in the extraction pipeline previously checked that scraped content
actually declared itself as belonging to the target place.
"""
from __future__ import annotations

from app.services.menu.extraction.entity_match import (
    extract_declared_entity_names,
    names_plausibly_match,
)


def _jsonld_html(name: str, type_: str = "Restaurant") -> str:
    return f"""
    <html><head>
    <script type="application/ld+json">
    {{"@context": "https://schema.org", "@type": "{type_}", "name": "{name}"}}
    </script>
    <title>Some Title</title>
    </head><body></body></html>
    """


def test_extracts_jsonld_restaurant_name():
    html = _jsonld_html("Itani Deli & Cafe")
    assert "Itani Deli & Cafe" in extract_declared_entity_names(html)


def test_extracts_title_tag_when_no_jsonld():
    html = "<html><head><title>Hopscotch Kitchen | Order Online</title></head></html>"
    names = extract_declared_entity_names(html)
    assert any("Hopscotch Kitchen" in n for n in names)


def test_extracts_og_site_name():
    html = (
        '<html><head><meta property="og:site_name" content="Hopscotch Kitchen">'
        "</head></html>"
    )
    assert "Hopscotch Kitchen" in extract_declared_entity_names(html)


def test_ignores_unrelated_jsonld_types():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@context": "https://schema.org", "@type": "BreadcrumbList", "name": "Home"}
    </script>
    </head></html>
    """
    assert extract_declared_entity_names(html) == []


def test_empty_html_returns_no_names():
    assert extract_declared_entity_names("") == []


def test_matching_name_passes():
    assert names_plausibly_match(["Itani Deli & Cafe"], "Itani Deli & Cafe") is True


def test_minor_formatting_differences_still_match():
    # A site's own page rarely restates the exact DB name -- suffixes and
    # punctuation shouldn't cause a false "different business" rejection.
    assert names_plausibly_match(["Itani Deli & Cafe | Order Online"], "Itani Deli Cafe") is True


def test_a_different_business_name_is_rejected():
    # The actual contamination shape: the iframe declares itself as a
    # completely different, unrelated business.
    assert names_plausibly_match(["Hopscotch Kitchen"], "Itani Deli & Cafe") is False


def test_no_declared_names_is_not_treated_as_a_mismatch():
    # No signal (title extraction failed, no JSON-LD) must not block --
    # this guard exists to catch a confirmed different business, not to
    # demand every page carry parseable identity metadata.
    assert names_plausibly_match([], "Itani Deli & Cafe") is True


def test_missing_expected_name_is_not_treated_as_a_mismatch():
    assert names_plausibly_match(["Hopscotch Kitchen"], None) is True
    assert names_plausibly_match(["Hopscotch Kitchen"], "") is True
