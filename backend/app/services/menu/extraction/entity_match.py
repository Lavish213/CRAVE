from __future__ import annotations

import json
import logging
import re
from difflib import SequenceMatcher
from typing import Iterable, List, Optional

from bs4 import BeautifulSoup


logger = logging.getLogger(__name__)


# schema.org types that plausibly carry a business's own declared name.
ENTITY_TYPES = {
    "restaurant",
    "localbusiness",
    "foodestablishment",
    "cafeorcoffeeshop",
    "barorpub",
    "bakery",
}

# Below this, a page's declared name is treated as "no real signal" rather
# than "confirmed mismatch" -- a title tag reduced to nothing after
# stripping boilerplate suffixes is not evidence either way.
MIN_COMPARABLE_NAME_LENGTH = 2

_SUFFIX_NOISE = re.compile(
    r"\b(restaurant|menu|order online|delivery|takeout|home|official site)\b",
    re.IGNORECASE,
)
_NON_ALNUM = re.compile(r"[^a-z0-9 ]")


def _normalize_name(name: str) -> str:
    name = _SUFFIX_NOISE.sub(" ", name.lower())
    name = _NON_ALNUM.sub(" ", name)
    return " ".join(name.split())


def _flatten_json_ld(data: object) -> Iterable[dict]:
    if isinstance(data, dict):
        yield data
        graph = data.get("@graph")
        if isinstance(graph, list):
            for entry in graph:
                yield from _flatten_json_ld(entry)
    elif isinstance(data, list):
        for entry in data:
            yield from _flatten_json_ld(entry)


def extract_declared_entity_names(html: str) -> List[str]:
    """
    Pull whatever name(s) a page declares for itself: schema.org JSON-LD
    Restaurant/LocalBusiness/etc. `name`, the <title> tag, and og:site_name.
    Best-effort and order-preserving; duplicates and empties are dropped.
    Returns [] when nothing usable is found -- callers should treat that as
    "no signal", not "confirmed mismatch".
    """
    if not html:
        return []

    names: List[str] = []
    seen = set()

    def _add(candidate: Optional[str]) -> None:
        if not candidate:
            return
        cleaned = candidate.strip()
        if not cleaned or cleaned.lower() in seen:
            return
        seen.add(cleaned.lower())
        names.append(cleaned)

    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:
        logger.debug("entity_match_parse_failed error=%s", exc)
        return []

    for script in soup.find_all("script", attrs={"type": "application/ld+json"}):
        try:
            raw = script.string or script.get_text() or ""
            if not raw.strip():
                continue
            data = json.loads(raw)
        except Exception:
            continue

        for obj in _flatten_json_ld(data):
            obj_type = obj.get("@type")
            type_names = (
                {t.lower() for t in obj_type}
                if isinstance(obj_type, list)
                else {str(obj_type).lower()} if obj_type else set()
            )
            if type_names & ENTITY_TYPES:
                _add(obj.get("name"))

    try:
        og_site_name = soup.find("meta", attrs={"property": "og:site_name"})
        if og_site_name:
            _add(og_site_name.get("content"))
    except Exception:
        pass

    try:
        if soup.title and soup.title.string:
            _add(str(soup.title.string))
    except Exception:
        pass

    return names


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def names_plausibly_match(
    declared_names: List[str],
    expected_name: Optional[str],
    *,
    threshold: float = 0.35,
) -> bool:
    """
    True when at least one declared name plausibly refers to expected_name,
    OR when there's no usable signal to compare (empty declared_names, or
    expected_name missing/too short after normalization) -- this check
    exists to catch a confirmed *different* business, not to demand every
    page perfectly restate the place's name. A single suffix-noise word
    (e.g. "Order Online") already gets stripped before comparing.
    """
    if not expected_name:
        return True

    normalized_expected = _normalize_name(expected_name)
    if len(normalized_expected) < MIN_COMPARABLE_NAME_LENGTH:
        return True

    if not declared_names:
        return True

    best = max(
        _similarity(normalized_expected, _normalize_name(candidate))
        for candidate in declared_names
    )
    return best >= threshold
