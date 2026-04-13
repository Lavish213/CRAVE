from __future__ import annotations

import csv
import json
from typing import List, Dict


def parse_menu_file(content: str) -> List[Dict]:

    items: List[Dict] = []

    try:

        data = json.loads(content)

        if isinstance(data, list):

            for row in data:

                items.append(
                    {
                        "name": row.get("name"),
                        "price": row.get("price"),
                        "section": row.get("section"),
                    }
                )

            return items

    except Exception:
        pass

    try:

        reader = csv.DictReader(content.splitlines())

        for row in reader:

            items.append(
                {
                    "name": row.get("name"),
                    "price": row.get("price"),
                    "section": row.get("section"),
                }
            )

    except Exception:
        pass

    return items