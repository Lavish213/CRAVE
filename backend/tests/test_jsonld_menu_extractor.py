from __future__ import annotations

import json

from app.services.menu.extraction.jsonld_menu_extractor import extract_jsonld_menu


def test_nested_restaurant_menu_extracts_leaf_items_with_sections():
    payload = {
        "@context": "https://schema.org",
        "@type": "Restaurant",
        "name": "Example Restaurant",
        "hasMenu": [
            {
                "@type": "Menu",
                "name": "Dinner Menu",
                "hasMenuSection": [
                    {
                        "@type": "MenuSection",
                        "name": "Appetizers",
                        "hasMenuItem": [
                            {
                                "@type": "MenuItem",
                                "name": "Deep-Fried Ravioli",
                                "description": "Garlic butter and parmesan.",
                                "offers": {"price": "9.50"},
                            },
                            {
                                "@type": "MenuItem",
                                "name": "Calamari",
                            },
                        ],
                    }
                ],
            }
        ],
    }
    html = (
        '<script type="application/ld+json">'
        + json.dumps(payload)
        + "</script>"
    )

    items = extract_jsonld_menu(html, "https://restaurant.test/menu")

    assert [item.name for item in items] == ["Deep-Fried Ravioli", "Calamari"]
    assert [item.section for item in items] == ["Appetizers", "Appetizers"]
    assert items[0].price_cents == 950
    assert items[1].price_cents is None


def test_menu_and_section_labels_are_not_emitted_as_items():
    payload = {
        "@type": "Restaurant",
        "hasMenu": {
            "@type": "Menu",
            "name": "Dinner Menu",
            "hasMenuSection": {
                "@type": "MenuSection",
                "name": "Mains",
                "hasMenuItem": {
                    "@type": "MenuItem",
                    "name": "Lasagna",
                },
            },
        },
    }
    html = (
        '<script type="application/ld+json">'
        + json.dumps(payload)
        + "</script>"
    )

    items = extract_jsonld_menu(html)

    assert [item.name for item in items] == ["Lasagna"]
