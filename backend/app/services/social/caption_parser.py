# app/services/social/caption_parser.py
from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional

_RE_HASHTAG = re.compile(r"#([A-Za-z0-9_]{2,})")
_RE_MENTION = re.compile(r"@([A-Za-z0-9._]{1,})")
_RE_LOC_LINE = re.compile(r"(?im)^(?:\s*(?:📍|location\s*[:\-]|loc\s*[:\-])\s*)(.+?)\s*$")
_RE_AT_IN = re.compile(r"(?i)\b(?:at|in)\s+([A-Za-z0-9][A-Za-z0-9'&\.\-\s]{2,60})")
_RE_CITY_ST = re.compile(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+){0,2})\s*,\s*([A-Z]{2})\b")
_RE_TRIM = re.compile(r"[\s\-\|•·:]+$")
_JUNK = frozenset({"tiktok", "instagram", "youtube", "reel", "shorts", "fyp", "foryou"})
_FOOD = frozenset({"food", "menu", "dish", "eat", "restaurant", "cafe", "diner", "brunch", "lunch", "dinner"})
_GEO_TAGS = frozenset({"oakland", "sf", "sanfrancisco", "bayarea", "sanjose", "la", "losangeles",
                        "nyc", "newyork", "chicago", "houston", "phoenix", "seattle", "portland"})


def _clean(s: str) -> Optional[str]:
    s = re.sub(r"\s+", " ", (s or "").strip())
    s = _RE_TRIM.sub("", s).strip()
    if not s or len(s) < 3 or len(s) > 80:
        return None
    if s.lower() in _JUNK or re.fullmatch(r"[\W_]+", s):
        return None
    return s


@dataclass(frozen=True)
class CaptionSignals:
    hashtags: list = field(default_factory=list)
    mentions: list = field(default_factory=list)
    location_lines: list = field(default_factory=list)
    place_candidates: list = field(default_factory=list)
    geo_hints: list = field(default_factory=list)
    has_food_terms: bool = False

    def to_dict(self) -> dict:
        return {
            "hashtags": self.hashtags,
            "mentions": self.mentions,
            "location_lines": self.location_lines,
            "place_candidates": self.place_candidates,
            "geo_hints": self.geo_hints,
            "has_food_terms": self.has_food_terms,
        }


def parse_caption(text: str | None) -> CaptionSignals:
    text = (text or "").strip()
    if not text:
        return CaptionSignals()

    hashtags = [m.group(1) for m in _RE_HASHTAG.finditer(text)][:25]
    mentions = [m.group(1) for m in _RE_MENTION.finditer(text)][:10]

    loc_lines = []
    for m in _RE_LOC_LINE.finditer(text):
        c = _clean(m.group(1))
        if c and c not in loc_lines:
            loc_lines.append(c)

    geo_hints = []
    for m in _RE_CITY_ST.finditer(text):
        h = f"{m.group(1).strip()}, {m.group(2).strip()}"
        if h not in geo_hints:
            geo_hints.append(h)
    for tag in hashtags:
        if tag.lower() in _GEO_TAGS and tag not in geo_hints:
            geo_hints.append(tag)

    candidates = list(loc_lines)
    for m in _RE_AT_IN.finditer(text):
        c = _clean(m.group(1))
        if not c:
            continue
        c = re.split(r"\b(?:for|with|and|but|because|when|where)\b", c, maxsplit=1, flags=re.IGNORECASE)[0].strip()
        c = _clean(c)
        if c and c not in candidates:
            candidates.append(c)

    has_food = bool(_FOOD.intersection(text.lower().split()))

    return CaptionSignals(
        hashtags=hashtags,
        mentions=mentions,
        location_lines=loc_lines,
        place_candidates=candidates[:10],
        geo_hints=geo_hints,
        has_food_terms=has_food,
    )
