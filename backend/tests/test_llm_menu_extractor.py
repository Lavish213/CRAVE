"""
Coverage for app.services.menu.extraction.llm_menu_extractor — the
last-resort DeepSeek-based menu extraction fallback.

Confirmed live against fishgutscalifornia.com: the page fetched fine (200,
real ~80KB HTML) and every one of the 7 pattern-based extractors still
found 0 items — the content was present, just structured in a way no
heuristic recognized. This is the fallback for exactly that failure mode.
"""
from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from app.services.menu.extraction.llm_menu_extractor import (
    _parse_items,
    _strip_to_text,
    extract_llm_menu,
)

SAMPLE_HTML = """
<html>
<head><script>var x = 1;</script><style>.a{color:red}</style></head>
<body>
<nav>Home | About | Menu</nav>
<header>Fish Guts California</header>
<h2>Starters</h2>
<p>Calamari - $14.50 - Crispy fried squid</p>
<h2>Entrees</h2>
<p>Fish Tacos - $16.00</p>
<footer>123 Main St</footer>
</body>
</html>
"""


def _mock_response(status_code=200, content="[]"):
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = {
        "choices": [{"message": {"content": content}}]
    }
    return resp


# ---------------------------------------------------------------------------
# _strip_to_text
# ---------------------------------------------------------------------------

def test_strip_to_text_removes_script_style_nav_footer():
    text = _strip_to_text(SAMPLE_HTML)
    assert "var x = 1" not in text
    assert "color:red" not in text
    assert "Home | About | Menu" not in text
    assert "123 Main St" not in text
    assert "Calamari" in text
    assert "Fish Tacos" in text


def test_strip_to_text_falls_back_to_raw_on_parse_failure():
    # Not real HTML at all — BeautifulSoup still shouldn't raise, but
    # exercise the except path's behavior contract regardless.
    text = _strip_to_text("just plain text, no tags")
    assert "just plain text" in text


# ---------------------------------------------------------------------------
# _parse_items
# ---------------------------------------------------------------------------

def test_parse_items_happy_path():
    raw = json.dumps([
        {"name": "Calamari", "section": "Starters", "price_cents": 1450, "description": "Crispy fried squid"},
        {"name": "Fish Tacos", "section": "Entrees", "price_cents": 1600, "description": None},
    ])
    items = _parse_items(raw)
    assert len(items) == 2
    assert items[0].name == "Calamari"
    assert items[0].price_cents == 1450
    assert items[0].section == "Starters"
    assert items[0].source_type == "llm"
    assert items[1].description is None


def test_parse_items_strips_markdown_fence():
    raw = '```json\n[{"name": "Soup", "price_cents": 900}]\n```'
    items = _parse_items(raw)
    assert len(items) == 1
    assert items[0].name == "Soup"


def test_parse_items_empty_array_is_empty_list():
    assert _parse_items("[]") == []


def test_parse_items_malformed_json_returns_empty():
    assert _parse_items("not json at all") == []


def test_parse_items_non_list_json_returns_empty():
    assert _parse_items('{"name": "not a list"}') == []


def test_parse_items_skips_rows_with_no_name():
    raw = json.dumps([{"name": "", "price_cents": 100}, {"name": "Real Item"}])
    items = _parse_items(raw)
    assert len(items) == 1
    assert items[0].name == "Real Item"


def test_parse_items_invalid_price_becomes_none():
    raw = json.dumps([{"name": "Item", "price_cents": "not a number"}])
    items = _parse_items(raw)
    assert items[0].price_cents is None


# ---------------------------------------------------------------------------
# extract_llm_menu — end to end with the HTTP call mocked
# ---------------------------------------------------------------------------

def test_extract_llm_menu_returns_empty_without_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert extract_llm_menu(SAMPLE_HTML, "https://example.test") == []


def test_extract_llm_menu_returns_empty_for_empty_html(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    assert extract_llm_menu("", "https://example.test") == []


def test_extract_llm_menu_happy_path(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    content = json.dumps([{"name": "Calamari", "price_cents": 1450}])

    with patch("app.services.menu.extraction.llm_menu_extractor.requests.post") as mock_post:
        mock_post.return_value = _mock_response(content=content)
        items = extract_llm_menu(SAMPLE_HTML, "https://example.test")

    assert len(items) == 1
    assert items[0].name == "Calamari"
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["headers"]["Authorization"] == "Bearer sk-test"
    assert call_kwargs["json"]["model"] == "deepseek-chat"


def test_extract_llm_menu_returns_empty_on_non_200(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    with patch("app.services.menu.extraction.llm_menu_extractor.requests.post") as mock_post:
        mock_post.return_value = _mock_response(status_code=402)
        items = extract_llm_menu(SAMPLE_HTML, "https://example.test")
    assert items == []


def test_extract_llm_menu_returns_empty_on_network_error(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    with patch("app.services.menu.extraction.llm_menu_extractor.requests.post") as mock_post:
        mock_post.side_effect = RuntimeError("connection reset")
        items = extract_llm_menu(SAMPLE_HTML, "https://example.test")
    assert items == []


def test_extract_llm_menu_returns_empty_on_malformed_response_shape(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    with patch("app.services.menu.extraction.llm_menu_extractor.requests.post") as mock_post:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = {"unexpected": "shape"}
        mock_post.return_value = resp
        items = extract_llm_menu(SAMPLE_HTML, "https://example.test")
    assert items == []
