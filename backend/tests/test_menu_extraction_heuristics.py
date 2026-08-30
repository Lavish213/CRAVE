from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.extraction.extraction_result_ranker import (
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
