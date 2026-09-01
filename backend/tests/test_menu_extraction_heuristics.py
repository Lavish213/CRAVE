from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.extraction_result_ranker import (
    is_plausible_extraction_result,
    rank_extraction_results,
)
from app.services.menu.extraction.heuristics import dedupe_items as dedupe_heuristic_items
from app.services.menu.extraction.iframe_menu_extractor import _dedupe as dedupe_iframe_items
from app.services.menu.extraction.pattern_detectors import _dedupe as dedupe_pattern_items
from app.services.menu.extraction.pdf_menu_extractor import _dedupe as dedupe_pdf_items
from app.services.menu.extraction.provider_menu_fetcher import _dedupe_items as dedupe_provider_items
from app.services.menu.extraction.universal_menu_json_parser import _dedupe as dedupe_json_items
from app.services.menu.menu_extraction_router import (
    _dedupe as dedupe_router_items,
    _normalize_snapshot_items,
    extract_menu,
)
from app.services.menu.providers.provider_normalizer import normalize_items
from app.services.menu.providers.clover_extractor import _dedupe as dedupe_clover_items


def _items(prefix: str, *, priced: bool, count: int = 5) -> list[ExtractedMenuItem]:
    return [
        ExtractedMenuItem(
            name=f"{prefix} {index}",
            section="Mains",
            price_cents=1200 + index if priced else None,
            image_url=f"https://images.test/{index}.jpg",
        )
        for index in range(count)
    ]


def test_ranker_prefers_structured_prices_over_an_equivalent_unpriced_result():
    unpriced = {"extractor": "html", "items": _items("Unpriced", priced=False)}
    priced = {"extractor": "html", "items": _items("Priced", priced=True)}

    selected = rank_extraction_results([unpriced, priced])

    assert selected is not None
    assert selected["items"] == priced["items"]


def test_router_dedupe_preserves_same_dish_with_distinct_prices():
    variants = [
        ExtractedMenuItem(name="Taco", section="Mains", price_cents=500),
        ExtractedMenuItem(name="Taco", section="Mains", price_cents=700),
    ]

    assert dedupe_router_items(variants) == variants


def test_snapshot_projection_preserves_active_price_and_image_fields():
    item = ExtractedMenuItem(
        name="Taco",
        section="Mains",
        price_cents=725,
        image_url="https://images.test/taco.jpg",
    )

    assert _normalize_snapshot_items([item]) == [
        {
            "name": "Taco",
            "category": "Mains",
            "price": 7.25,
            "description": None,
            "image": "https://images.test/taco.jpg",
        }
    ]


@pytest.mark.parametrize(
    "dedupe",
    [
        dedupe_provider_items,
        dedupe_json_items,
        dedupe_pattern_items,
        dedupe_iframe_items,
        dedupe_heuristic_items,
        dedupe_pdf_items,
        dedupe_clover_items,
    ],
)
def test_active_integer_price_contract_never_crashes_deduplication(dedupe):
    item = ExtractedMenuItem(name="Taco", section="Mains", price_cents=725)

    assert dedupe([item]) == [item]


def test_provider_normalizer_uses_the_active_contract_and_preserves_cents():
    item = ExtractedMenuItem(
        name="  Taco  ",
        section=" Mains ",
        price_cents=725,
        description="  Crispy fish  ",
        image_url="https://images.test/taco.jpg",
        source_url="https://restaurant.test/menu",
    )

    normalized = normalize_items([item], provider="toast")

    assert normalized == [
        ExtractedMenuItem(
            name="Taco",
            section="Mains",
            price_cents=725,
            description="Crispy fish",
            image_url="https://images.test/taco.jpg",
            provider="toast",
            source_url="https://restaurant.test/menu",
        )
    ]


def test_two_vendor_merge_shaped_result_is_rejected():
    """
    Reproduces the shape of a real production contamination incident: two
    vendors' menus concatenated into one 112-item result via a shared
    iframe/API widget, where common dish names (fries, salad, burger) each
    appear once per vendor -- 56 distinct names across 112 items is a 0.5
    unique ratio, which cleared the old >= 0.5 floor and got materialized
    as a single restaurant's menu. A genuine single-vendor menu essentially
    never repeats half its names; this must now be rejected.
    """
    common_dish_names = [f"Dish {i}" for i in range(55)] + ["Fries"]
    two_vendor_merge = [
        ExtractedMenuItem(name=name, section="Vendor A", price_cents=1000)
        for name in common_dish_names
    ] + [
        ExtractedMenuItem(name=name, section="Vendor B", price_cents=1100)
        for name in common_dish_names
    ]
    assert len(two_vendor_merge) == 112

    assert is_plausible_extraction_result(two_vendor_merge) is False


def test_a_real_menus_incidental_repeats_still_pass():
    """A real single-vendor menu can legitimately repeat a handful of names
    (e.g. a side dish offered under multiple sections) without approaching
    the two-vendor-merge signature above -- this must still pass."""
    mostly_unique = _items("Dish", priced=True, count=40)
    a_few_repeats = [
        ExtractedMenuItem(name="Fries", section="Sides", price_cents=400),
        ExtractedMenuItem(name="Fries", section="Kids Menu", price_cents=300),
    ]
    menu = mostly_unique + a_few_repeats

    assert is_plausible_extraction_result(menu) is True


def _iframe_scenario(*, iframe_title: str, place_name: str | None):
    """
    Drives extract_menu() all the way down to iframe extraction (every
    cheaper tier finds nothing), with one iframe whose page declares
    `iframe_title` as its own identity. Returns whatever items survive.
    """
    iframe_html = f"<html><head><title>{iframe_title}</title></head></html>"
    contaminating_items = _items("Contaminating Item", priced=True, count=5)
    fake_response = SimpleNamespace(status_code=200, text=iframe_html)

    def _html_extract_side_effect(html, url=None, source_url=None):
        if html == iframe_html:
            return contaminating_items
        return []

    with (
        patch("app.services.menu.menu_extraction_router.detect_provider", return_value=None),
        patch("app.services.menu.menu_extraction_router.extract_hydration_menu", return_value=[]),
        patch("app.services.menu.menu_extraction_router.extract_jsonld_menu", return_value=[]),
        patch("app.services.menu.menu_extraction_router.extract_menu_from_js", return_value=[]),
        patch("app.services.menu.menu_extraction_router.discover_api_endpoints", return_value=[]),
        patch(
            "app.services.menu.menu_extraction_router.extract_html_menu",
            side_effect=_html_extract_side_effect,
        ),
        patch(
            "app.services.menu.menu_extraction_router.detect_menu_iframes",
            return_value=["https://widget.test/iframe"],
        ),
        patch("app.services.menu.menu_extraction_router.fetch", return_value=fake_response),
        patch("app.services.menu.menu_extraction_router.fetch_with_browser", return_value=None),
    ):
        return extract_menu(
            "<html>menu</html>",
            url="https://itani.test",
            place_name=place_name,
            allow_llm_fallback=False,
        )


def test_iframe_from_an_unrelated_business_is_dropped():
    """
    The actual production incident's mechanism: a restaurant's own page
    embeds an iframe (an ordering widget) that turns out to declare a
    completely different business's identity. Without place_name to check
    against, this content used to get scraped and materialized as if it
    were the target restaurant's own menu.
    """
    result = _iframe_scenario(iframe_title="Hopscotch Kitchen", place_name="Itani Deli & Cafe")
    assert result == []


def test_iframe_from_the_same_business_is_still_used():
    """The guard must not reject legitimate same-business iframe content --
    this proves it's a targeted check, not a blanket iframe block."""
    result = _iframe_scenario(iframe_title="Itani Deli & Cafe", place_name="Itani Deli & Cafe")
    assert len(result) == 5


def test_navigation_heavy_html_does_not_bypass_the_quality_ladder():
    junk = [
        ExtractedMenuItem(name=name, source_type="html")
        for name in (
            "Home",
            "About",
            "Contact",
            "Locations",
            "Login",
            "Register",
            "Menu",
            "Order",
            "Delivery",
            "Account",
            "Sign in",
            "Menus",
        )
    ]
    real = _items("Dish", priced=True)

    with (
        patch("app.services.menu.menu_extraction_router.detect_provider", return_value=None),
        patch("app.services.menu.menu_extraction_router.extract_hydration_menu", return_value=[]),
        patch("app.services.menu.menu_extraction_router.extract_jsonld_menu", return_value=real),
        patch("app.services.menu.menu_extraction_router.extract_menu_from_js", return_value=[]),
        patch("app.services.menu.menu_extraction_router.discover_api_endpoints", return_value=[]),
        patch("app.services.menu.menu_extraction_router.extract_html_menu", return_value=junk),
        patch("app.services.menu.menu_extraction_router.detect_menu_iframes", return_value=[]),
    ):
        result = extract_menu("<html>menu</html>", url="https://restaurant.test")

    assert result == real
