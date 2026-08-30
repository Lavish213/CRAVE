from __future__ import annotations

import hashlib
import json
from typing import Any, Optional


def _coverage(items: list[dict[str, Any]], field: str) -> float:
    if not items:
        return 0.0
    populated = sum(1 for item in items if item.get(field) not in (None, ""))
    return round(populated / len(items), 3)


def build_snapshot_evidence(items: list[dict[str, Any]]) -> dict[str, Any]:
    stable_rows = sorted(
        (
            {
                "name": item.get("name"),
                "category": item.get("category"),
                "price": item.get("price"),
            }
            for item in items
        ),
        key=lambda row: (
            str(row.get("name") or "").lower(),
            str(row.get("category") or "").lower(),
            str(row.get("price") or ""),
        ),
    )
    serialized = json.dumps(stable_rows, sort_keys=True, separators=(",", ":"))

    return {
        "description_coverage": _coverage(items, "description"),
        "fingerprint": hashlib.sha256(serialized.encode("utf-8")).hexdigest(),
        "image_coverage": _coverage(items, "image"),
        "item_count": len(items),
        "price_coverage": _coverage(items, "price"),
        "section_coverage": _coverage(items, "category"),
    }


def compare_snapshot_evidence(
    current: dict[str, Any],
    previous: Optional[dict[str, Any]],
) -> dict[str, Any]:
    if not previous:
        return {"status": "baseline", "item_count_drop": 0.0}

    previous_count = int(previous.get("item_count") or 0)
    current_count = int(current.get("item_count") or 0)
    item_count_drop = (
        round(max(previous_count - current_count, 0) / previous_count, 3)
        if previous_count
        else 0.0
    )
    price_drop = round(
        max(
            float(previous.get("price_coverage") or 0.0)
            - float(current.get("price_coverage") or 0.0),
            0.0,
        ),
        3,
    )

    if item_count_drop >= 0.5 or price_drop >= 0.4:
        status = "regressed"
    elif current.get("fingerprint") == previous.get("fingerprint"):
        status = "stable"
    else:
        status = "changed"

    return {
        "status": status,
        "item_count_drop": item_count_drop,
        "price_coverage_drop": price_drop,
    }
