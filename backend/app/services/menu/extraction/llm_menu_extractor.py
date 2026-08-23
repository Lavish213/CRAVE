"""
LLM-based menu extraction — the last-resort fallback for pages where real,
successfully-fetched content defeats every pattern-based extractor above it
(no JSON-LD, no recognized hydration state, no discoverable API endpoint,
HTML structure the selector-based extractor doesn't recognize).

Confirmed live in production against fishgutscalifornia.com: the page
fetched fine (200 OK, ~80KB of real HTML) and every heuristic extractor
still found 0 items — the content was present, just structured in a way
none of the pattern-based extractors recognized. Browser escalation
doesn't fix this class of failure either, since the content was already
in the plain-fetched HTML, not JS-injected after load.

Deliberately the LAST strategy tried, never a replacement for the others —
structured-data extraction is cheaper and more precise when it works; this
only runs once nothing else found enough items (see menu_extraction_router.py).

Uses DeepSeek's OpenAI-compatible chat completions API rather than
Anthropic — see CRAVE_REMAINING_WORK.md for the cost comparison that
motivated the choice for this specific, high-volume, low-complexity
extraction task (bounded structured extraction, not open-ended reasoning).
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import List, Optional

import requests
from bs4 import BeautifulSoup

from app.services.menu.contracts import ExtractedMenuItem

logger = logging.getLogger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
DEEPSEEK_MODEL = "deepseek-chat"

_TIMEOUT = 30
# Keeps input comfortably in the low thousands of tokens — the whole point
# of stripping first is to avoid paying for nav/script/style noise.
_MAX_TEXT_CHARS = 12000

_STRIP_TAGS = ("script", "style", "nav", "footer", "header", "svg", "noscript")

_SYSTEM_PROMPT = (
    "You extract restaurant menu items from webpage text. Return ONLY a "
    "JSON array of objects, no prose, no markdown fences. Each object: "
    '{"name": str, "section": str or null, "price_cents": int or null, '
    '"description": str or null}. price_cents is the price in cents as an '
    "integer (e.g. $12.50 -> 1250), or null if no price is shown. "
    "Include only actual food/drink menu items — skip navigation, hours, "
    "addresses, reviews, and unrelated page text. If there is no menu in "
    "the text, return an empty array []."
)


def _strip_to_text(html: str) -> str:
    try:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(_STRIP_TAGS):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        return text[:_MAX_TEXT_CHARS]
    except Exception as exc:
        logger.debug("llm_extract_strip_failed error=%s", exc)
        return html[:_MAX_TEXT_CHARS]


def _parse_items(raw: str) -> List[ExtractedMenuItem]:
    raw = (raw or "").strip()

    # The model occasionally wraps output in a markdown fence despite the
    # system prompt saying not to — pull the array out rather than failing.
    match = re.search(r"\[.*\]", raw, re.DOTALL)
    if match:
        raw = match.group(0)

    try:
        data = json.loads(raw)
    except Exception as exc:
        logger.debug("llm_extract_parse_failed error=%s", exc)
        return []

    if not isinstance(data, list):
        return []

    items: List[ExtractedMenuItem] = []
    for row in data:
        if not isinstance(row, dict):
            continue

        name = str(row.get("name") or "").strip()
        if not name:
            continue

        price_cents = row.get("price_cents")
        try:
            price_cents = int(price_cents) if price_cents is not None else None
        except (TypeError, ValueError):
            price_cents = None

        section = row.get("section")
        description = row.get("description")

        items.append(
            ExtractedMenuItem(
                name=name,
                section=str(section).strip() or None if section else None,
                price_cents=price_cents,
                description=str(description).strip() or None if description else None,
                source_type="llm",
            )
        )

    return items


def extract_llm_menu(html: str, url: Optional[str] = None) -> List[ExtractedMenuItem]:
    """
    Last-resort menu extraction via DeepSeek. Returns [] on any failure —
    missing API key, network error, malformed response — never raises, so
    it's always safe to call unconditionally from the extraction router.
    """
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    if not api_key or not html:
        return []

    text = _strip_to_text(html)
    if not text:
        return []

    try:
        resp = requests.post(
            DEEPSEEK_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "model": DEEPSEEK_MODEL,
                "messages": [
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                "temperature": 0,
                "max_tokens": 4096,
            },
            timeout=_TIMEOUT,
        )
    except Exception as exc:
        logger.warning("llm_extract_request_failed url=%s error=%s", url, exc)
        return []

    if resp.status_code != 200:
        logger.warning(
            "llm_extract_upstream_error url=%s status=%s", url, resp.status_code
        )
        return []

    try:
        content = resp.json()["choices"][0]["message"]["content"]
    except Exception as exc:
        logger.warning("llm_extract_response_shape_error url=%s error=%s", url, exc)
        return []

    items = _parse_items(content)
    logger.info("llm_extract_result url=%s count=%s", url, len(items))
    return items
