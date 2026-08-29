from __future__ import annotations

import ast
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from bs4 import BeautifulSoup

from app.services.menu.extraction.jsonld_menu_extractor import extract_jsonld_menu
from app.services.menu.extraction.pattern_detectors import detect_menu_patterns
from app.services.menu.extraction.universal_menu_json_parser import (
    parse_universal_menu_json,
)
from app.services.menu.extraction.js.js_extraction_service import extract_menu_from_js
from app.db.models.menu_snapshot import MenuSnapshot
from app.db.session import SessionLocal
from app.pipeline.snapshot_writer import MenuSnapshotWriter
from app.services.menu.menu_diagnostics import _analyze_snapshots


MENU_SERVICE_ROOT = Path(__file__).parents[1] / "app" / "services" / "menu"
BACKEND_ROOT = Path(__file__).parents[1]
SEED_PLACE_ID = "00000000-0000-0000-0000-000000000002"


def test_every_extracted_menu_item_constructor_uses_the_active_price_contract():
    legacy_calls: list[str] = []

    for source_path in MENU_SERVICE_ROOT.rglob("*.py"):
        tree = ast.parse(source_path.read_text(encoding="utf-8"))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue

            is_item_constructor = (
                isinstance(node.func, ast.Name)
                and node.func.id == "ExtractedMenuItem"
            ) or (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "ExtractedMenuItem"
            )
            if not is_item_constructor:
                continue

            if any(keyword.arg == "price" for keyword in node.keywords):
                legacy_calls.append(f"{source_path.relative_to(MENU_SERVICE_ROOT)}:{node.lineno}")

    assert legacy_calls == []


def test_jsonld_replay_preserves_price_cents():
    html = """
    <script type="application/ld+json">
      {"@type":"MenuItem","name":"Fish Taco","offers":{"price":"7.25"}}
    </script>
    """

    items = extract_jsonld_menu(html, "https://restaurant.test/menu")

    assert [(item.name, item.price_cents) for item in items] == [("Fish Taco", 725)]


def test_pattern_replay_preserves_price_cents():
    soup = BeautifulSoup(
        '<div class="menu-item">Fish Taco <span>$7.25</span></div>',
        "html.parser",
    )

    items = detect_menu_patterns(soup)

    assert len(items) == 1
    assert items[0].price_cents == 725


def test_universal_payload_replay_preserves_price_and_image():
    payload = {
        "categories": [
            {
                "name": "Mains",
                "items": [
                    {
                        "name": "Fish Taco",
                        "price": "7.25",
                        "image_url": "https://images.test/taco.jpg",
                    }
                ],
            }
        ]
    }

    items = parse_universal_menu_json(payload)

    assert len(items) == 1
    assert items[0].price_cents == 725
    assert items[0].image_url == "https://images.test/taco.jpg"


def test_snapshot_writer_records_coverage_and_detects_item_count_regression():
    db = SessionLocal()
    try:
        db.query(MenuSnapshot).filter(MenuSnapshot.place_id == SEED_PLACE_ID).delete()
        db.commit()
    finally:
        db.close()

    writer = MenuSnapshotWriter()
    baseline_items = [
        {
            "name": f"Dish {index}",
            "category": "Mains",
            "price": 10 + index,
            "description": "Fresh",
            "image": f"https://images.test/{index}.jpg",
        }
        for index in range(10)
    ]
    regressed_items = baseline_items[:3]

    first_id = writer.write(
        place_id=SEED_PLACE_ID,
        extraction_method="html",
        source_url="https://restaurant.test/menu",
        normalized_items=baseline_items,
    )
    second_id = writer.write(
        place_id=SEED_PLACE_ID,
        extraction_method="html",
        source_url="https://restaurant.test/menu",
        normalized_items=regressed_items,
    )

    db = SessionLocal()
    try:
        first = db.get(MenuSnapshot, first_id)
        second = db.get(MenuSnapshot, second_id)

        assert first.raw_payload["evidence"] == {
            "description_coverage": 1.0,
            "fingerprint": first.raw_payload["evidence"]["fingerprint"],
            "image_coverage": 1.0,
            "item_count": 10,
            "price_coverage": 1.0,
            "section_coverage": 1.0,
        }
        assert first.raw_payload["drift"]["status"] == "baseline"
        assert second.raw_payload["drift"]["status"] == "regressed"
        assert second.raw_payload["drift"]["item_count_drop"] == 0.7
    finally:
        db.query(MenuSnapshot).filter(MenuSnapshot.place_id == SEED_PLACE_ID).delete()
        db.commit()
        db.close()


def test_js_recipe_memory_only_learns_endpoints_that_produce_menu_items():
    good_endpoint = {"url": "https://restaurant.test/api/menu", "method": "GET", "score": 10}
    bad_endpoint = {"url": "https://restaurant.test/api/navigation", "method": "GET", "score": 9}
    menu_payload = [
        {"name": f"Dish {index}", "price": 1000 + index}
        for index in range(5)
    ]

    with (
        patch("app.services.menu.extraction.js.js_extraction_service.detect_hydration_state", return_value=None),
        patch("app.services.menu.extraction.js.js_extraction_service.get_remembered_endpoints", return_value=[]),
        patch("app.services.menu.extraction.js.js_extraction_service._collect_bundles", return_value=["bundle.js"]),
        patch("app.services.menu.extraction.js.js_extraction_service._load_bundles", return_value={"bundle.js": "code"}),
        patch("app.services.menu.extraction.js.js_extraction_service._discover_endpoints", return_value=[good_endpoint, bad_endpoint]),
        patch("app.services.menu.extraction.js.js_extraction_service.rank_js_endpoints", side_effect=lambda endpoints: endpoints),
        patch(
            "app.services.menu.extraction.js.js_extraction_service.replay_js_endpoints",
            return_value=[
                {**good_endpoint, "payload": menu_payload, "status": 200},
                {**bad_endpoint, "payload": {"links": ["Home", "About"]}, "status": 200},
            ],
        ),
        patch("app.services.menu.extraction.js.js_extraction_service.remember_endpoints") as remember,
    ):
        items = extract_menu_from_js("<script src='bundle.js'></script>", "https://restaurant.test")

    assert len(items) == 5
    remember.assert_called_once_with("https://restaurant.test", [good_endpoint])


def test_replay_corpus_cli_passes_all_sandbox_fixtures():
    manifest = BACKEND_ROOT / "tests" / "fixtures" / "menu_extraction" / "manifest.json"
    completed = subprocess.run(
        [
            sys.executable,
            str(BACKEND_ROOT / "scripts" / "run_menu_extraction_corpus.py"),
            "--manifest",
            str(manifest),
            "--json",
        ],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    report = json.loads(completed.stdout)
    assert report["failed"] == 0
    assert report["passed"] == 3


def test_snapshot_diagnostics_aggregate_coverage_and_regressions():
    snapshots = [
        MenuSnapshot(
            place_id=SEED_PLACE_ID,
            extraction_method="html",
            success=True,
            item_count=10,
            raw_payload={
                "evidence": {"price_coverage": 1.0, "image_coverage": 0.8},
                "drift": {"status": "baseline"},
            },
        ),
        MenuSnapshot(
            place_id=SEED_PLACE_ID,
            extraction_method="html",
            success=True,
            item_count=3,
            raw_payload={
                "evidence": {"price_coverage": 0.5, "image_coverage": 0.2},
                "drift": {"status": "regressed"},
            },
        ),
    ]

    stats = _analyze_snapshots(snapshots)

    assert stats["avg_price_coverage"] == 0.75
    assert stats["avg_image_coverage"] == 0.5
    assert stats["regression_count"] == 1
