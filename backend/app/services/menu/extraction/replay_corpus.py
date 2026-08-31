from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.services.menu.menu_extraction_router import extract_menu


def run_replay_manifest(manifest_path: str | Path) -> dict[str, Any]:
    path = Path(manifest_path).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    cases = manifest.get("cases") if isinstance(manifest, dict) else None
    if not isinstance(cases, list):
        raise ValueError("replay manifest must contain a cases list")

    results: list[dict[str, Any]] = []

    for case in cases:
        case_id = str(case.get("id") or "unnamed")
        fixture_path = (path.parent / str(case.get("fixture") or "")).resolve()
        if path.parent not in fixture_path.parents:
            raise ValueError(f"fixture escapes manifest directory: {case_id}")

        html = fixture_path.read_text(encoding="utf-8")
        items = extract_menu(
            html,
            url=case.get("url"),
            place_id=None,
            allow_network_fallbacks=False,
            allow_llm_fallback=False,
        )
        names = {item.name for item in items if item.name}
        expected_names = set(case.get("expected_names") or [])
        min_items = int(case.get("min_items") or 0)
        max_items_raw = case.get("max_items")
        max_items = int(max_items_raw) if max_items_raw is not None else None
        priced = sum(1 for item in items if item.price_cents is not None)
        price_coverage = round(priced / len(items), 3) if items else 0.0
        min_price_coverage = float(case.get("min_price_coverage") or 0.0)

        failures: list[str] = []
        if len(items) < min_items:
            failures.append(f"item_count {len(items)} < {min_items}")
        if max_items is not None and len(items) > max_items:
            failures.append(f"item_count {len(items)} > {max_items}")
        missing_names = sorted(expected_names - names)
        if missing_names:
            failures.append(f"missing_names={missing_names}")
        if price_coverage < min_price_coverage:
            failures.append(
                f"price_coverage {price_coverage} < {min_price_coverage}"
            )

        results.append(
            {
                "id": case_id,
                "item_count": len(items),
                "price_coverage": price_coverage,
                "status": "passed" if not failures else "failed",
                "failures": failures,
            }
        )

    passed = sum(1 for result in results if result["status"] == "passed")
    return {
        "version": manifest.get("version"),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "cases": results,
    }
