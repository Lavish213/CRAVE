from __future__ import annotations

from app.services.menu.contracts import ExtractedMenuItem
from app.services.menu.providers import provider_registry


def _items(prefix: str, count: int = 2) -> list[ExtractedMenuItem]:
    return [
        ExtractedMenuItem(name=f"{prefix} {index}", price_cents=1000 + index)
        for index in range(count)
    ]


def test_url_only_provider_receives_url_without_extra_html_argument(monkeypatch):
    calls: list[str] = []

    def url_only(url: str) -> list[ExtractedMenuItem]:
        calls.append(url)
        return _items("Direct")

    monkeypatch.setitem(provider_registry._PROVIDER_REGISTRY, "contract", [url_only])

    result = provider_registry.extract_with_fallback(
        "contract",
        "https://restaurant.test/menu",
        "<html>ignored</html>",
    )

    assert calls == ["https://restaurant.test/menu"]
    assert [item.name for item in result] == ["Direct 0", "Direct 1"]


def test_html_url_provider_receives_html_first_and_url_second(monkeypatch):
    calls: list[tuple[str | None, str | None]] = []

    def html_url(
        html: str | None = None,
        url: str | None = None,
    ) -> list[ExtractedMenuItem]:
        calls.append((html, url))
        return _items("Embedded")

    monkeypatch.setitem(provider_registry._PROVIDER_REGISTRY, "contract", [html_url])

    result = provider_registry.extract_with_fallback(
        "contract",
        "https://restaurant.test/menu",
        "<html>menu payload</html>",
    )

    assert calls == [
        ("<html>menu payload</html>", "https://restaurant.test/menu")
    ]
    assert [item.name for item in result] == ["Embedded 0", "Embedded 1"]
