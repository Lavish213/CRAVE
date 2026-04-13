from __future__ import annotations

from typing import List, Dict


MENU_KEYWORDS = [
    "menu",
    "menus",
]


MENU_EXTENSIONS = [
    ".json",
    ".csv",
    ".md",
    ".txt",
]


def detect_menu_files(files: List[Dict]) -> List[Dict]:

    results: List[Dict] = []

    for f in files:

        name = (f.get("name") or "").lower()

        if any(k in name for k in MENU_KEYWORDS):

            if any(name.endswith(ext) for ext in MENU_EXTENSIONS):

                results.append(f)

    return results