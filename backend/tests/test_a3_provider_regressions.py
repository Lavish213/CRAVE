import httpx

from app.services.menu.extraction.js.js_hydration_detector import (
    detect_hydration_state,
)
from app.services.network.block_classifier import classify_response
from app.services.network.http_fetcher import _validate_html_body


def test_zero_signal_json_payload_is_not_menu_hydration():
    html = '<script type="application/json">{"name":"Itani Ramen"}</script>'

    assert detect_hydration_state(html) == {}


def test_benign_cloudflare_feature_flag_is_not_a_bot_challenge():
    html = """
    <html><body>
      <main>Restaurant homepage with ordinary public content.</main>
      <script>
        window.flags = {"ecom-checkout-cloudflare-challenge-recovery": true};
      </script>
    </body></html>
    """

    result = classify_response(
        status_code=200,
        text=html,
        final_url="https://www.reemscalifornia.com/",
    )

    assert result.is_blocked is False
    assert result.reason == "ok"


def test_real_cloudflare_challenge_marker_remains_blocked():
    html = "<html><body><form id='cf-challenge'>Verify you are human</form></body></html>"

    result = classify_response(
        status_code=200,
        text=html,
        final_url="https://example.com/",
    )

    assert result.is_blocked is True
    assert result.reason == "cloudflare_challenge"


def test_http_fetcher_allows_benign_cloudflare_feature_flag():
    html = """
    <html><body>
      <main>Restaurant homepage with ordinary public content.</main>
      <script>
        window.flags = {"ecom-checkout-cloudflare-challenge-recovery": true};
      </script>
    </body></html>
    """
    response = httpx.Response(
        200,
        headers={"content-type": "text/html"},
        text=html,
    )

    _validate_html_body(response)


def test_http_fetcher_still_rejects_real_cloudflare_challenge():
    html = (
        "<html><body><main>Attention required! | Cloudflare</main>"
        "<p>This page is intentionally long enough to pass the empty-page guard. "
        "The challenge-specific marker must be what causes rejection here.</p>"
        "<form id='cf-challenge'>Verify you are human</form></body></html>"
    )
    response = httpx.Response(
        200,
        headers={"content-type": "text/html"},
        text=html,
    )

    try:
        _validate_html_body(response)
    except RuntimeError as exc:
        assert str(exc) == "blocked_html"
    else:
        raise AssertionError("real Cloudflare challenge should remain blocked")
