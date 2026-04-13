from __future__ import annotations

from typing import List, Dict


def normalize_menu_items(items: List[Dict]) -> List[Dict]:

    normalized: List[Dict] = []

    for item in items:

        name = item.get("name")

        if not name:
            continue

        normalized.append(
            {
                "name": name.strip(),
                "section": item.get("section"),
                "price": item.get("price"),
            }
        )

    return normalized