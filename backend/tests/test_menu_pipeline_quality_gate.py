"""
Coverage for app.services.menu.menu_pipeline.process_extracted_menu's
quality gate (_is_low_quality) -- the ONE gate common to every menu-writing
path. MenuOrchestrator.run_for_place() AND run_with_items() (the latter
used by MasterDataOrchestrator -> ExtractionController, a completely
separate extraction implementation from menu_extraction_router.py) both
call process_extracted_menu() before ever emitting claims, so a check
added here protects both -- unlike extraction_result_ranker.py's
uniqueness gate, which only guards menu_extraction_router.py's own
iframe tier.

Previously untested despite being the pipeline's actual last line of
defense before materialization.
"""
from __future__ import annotations

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.menu_pipeline import process_extracted_menu


def _item(name: str, section: str, price_cents: int = 1000) -> ExtractedMenuItem:
    return ExtractedMenuItem(name=name, section=section, price_cents=price_cents)


def test_two_vendor_merge_across_different_sections_is_rejected():
    """
    Reproduces the actual production incident's real shape: two vendors'
    menus merged via a shared iframe/API widget, each contributing its own
    section -- so the fingerprint pre-dedup (name+section+currency) never
    collapses the repeated common dish names, and 112 rows with only ~56
    distinct names reach this gate. Every item is realistically priced, so
    only the new uniqueness check catches this -- the existing
    "4+ items, zero priced" check does not.
    """
    common_dish_names = [f"Dish {i}" for i in range(55)] + ["Fries"]
    items = [
        _item(name, section="Vendor A") for name in common_dish_names
    ] + [
        _item(name, section="Vendor B") for name in common_dish_names
    ]
    assert len(items) == 112

    menu = process_extracted_menu(items)

    assert menu.item_count == 0
    assert menu.sections == []


def test_a_real_menus_incidental_cross_section_repeat_still_passes():
    """A legitimate single-vendor menu can repeat a side dish across
    sections (e.g. Fries under both Sides and Kids Menu) without
    approaching the two-vendor-merge signature above."""
    items = [_item(f"Dish {i}", section="Mains") for i in range(20)] + [
        _item("Fries", section="Sides"),
        _item("Fries", section="Kids Menu"),
    ]

    menu = process_extracted_menu(items)

    assert menu.item_count == 22


def test_existing_too_few_unique_names_check_still_rejects():
    items = [_item("Fries", section="Sides"), _item("Fries", section="Kids Menu")]
    # Same name in two sections -> 2 rows survive fingerprint dedup, but
    # only 1 distinct name -- below MIN_VALID_ITEMS (2).
    menu = process_extracted_menu(items)
    assert menu.item_count == 0


def test_existing_all_unpriced_large_result_still_rejects():
    items = [_item(f"Dish {i}", section="Mains", price_cents=None) for i in range(5)]
    menu = process_extracted_menu(items)
    assert menu.item_count == 0
