from __future__ import annotations

import gzip
import logging
import time
import zlib
from typing import Any, Optional
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from app.services.network.anti_bot_profiles import get_sticky_profile, should_warm_host
from app.services.network.block_classifier import classify_exception, classify_response
from app.services.network.browser_escalation import fetch_with_browser
from app.services.network.cookie_jar import get_cookie_header, update_cookies
from app.services.network.domain_policy import get_domain_policy
from app.services.network.domain_rate_limiter import penalize_domain, wait_for_domain
from app.services.network.http_client import get_http_client, reset_http_client
from app.services.network.impersonation_fetcher import fetch_impersonated
from app.services.network.redirect_guard import should_follow_redirect, update_history
from app.services.network.request_strategy import build_request_strategy


logger = logging.getLogger(__name__)


MAX_HTML_BYTES = 5 * 1024 * 1024
MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_BINARY_BYTES = 10 * 1024 * 1024
MAX_REDIRECTS = 8

DEFAULT_TIMEOUT = 6.0
WARMUP_TIMEOUT = 4.0
MAX_TOTAL_TIME = 10.0
MIN_HTML_TEXT_LENGTH = 200

_BLOCKED_HTML_TOKENS = (
    "access denied",
    "forbidden",
    "captcha",
    "cloudflare",
    "verify you are human",
    "attention required",
    "temporarily unavailable",
    "bot detection",
)


def _within_time_budget(start: float, limit: float = MAX_TOTAL_TIME) -> bool:
    return (time.monotonic() - start) <= limit


def _host(url: str) -> str:
    try:
        return (urlparse(url).netloc or "").lower() or "unknown"
    except Exception:
        return "unknown"


def _origin(url: str) -> str:
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}"


def _origin_or_none(url: Optional[str]) -> Optional[str]:
    if not url:
        return None
    value = _origin(url)
    return value or None


def _strip_fragment(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            "",
        )
    )


def _profile_for_host(host: str) -> dict[str, str]:
    return get_sticky_profile(host)


def _site_relation(url: str, referer: Optional[str]) -> str:
    if not referer:
        return "none"

    target = _origin_or_none(url)
    ref = _origin_or_none(referer)

    if not target or not ref:
        return "none"

    if target == ref:
        return "same-origin"

    target_host = _host(url)
    ref_host = _host(referer)

    if target_host.endswith("." + ref_host) or ref_host.endswith("." + target_host):
        return "same-site"

    return "cross-site"


def _is_toast_host(url: str) -> bool:
    return "toasttab.com" in _host(url)


def _build_headers(
    url: str,
    *,
    mode: str,
    method: str,
    referer: Optional[str],
) -> dict[str, str]:
    host = _host(url)
    profile = _profile_for_host(host)
    method = method.upper()

    headers: dict[str, str] = {
        **profile,
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Connection": "keep-alive",
    }

    site_relation = _site_relation(url, referer)
    target_origin = _origin_or_none(url)
    referer_origin = _origin_or_none(referer)

    if mode == "document":
        headers.update(
            {
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": site_relation,
            }
        )
        if method == "GET":
            headers["Sec-Fetch-User"] = "?1"

    elif mode == "script":
        headers.update(
            {
                "Accept": "*/*",
                "Sec-Fetch-Dest": "script",
                "Sec-Fetch-Mode": "no-cors",
                "Sec-Fetch-Site": site_relation if referer else "same-origin",
            }
        )

    elif mode in ("api", "graphql"):
        headers.update(
            {
                "Accept": "application/json, text/plain, */*",
                "Sec-Fetch-Dest": "empty",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Site": site_relation if referer else "same-origin",
            }
        )
        if method != "GET":
            headers["Content-Type"] = "application/json"

    else:
        headers["Accept"] = "*/*"

    if referer:
        headers["Referer"] = _strip_fragment(referer)

    if referer_origin and mode in ("api", "graphql"):
        headers["Origin"] = referer_origin
    elif target_origin and method != "GET":
        headers["Origin"] = target_origin

    if _is_toast_host(url):
        headers["Referer"] = "https://www.toasttab.com/"
        if mode in ("api", "graphql"):
            headers["Origin"] = "https://www.toasttab.com"
        headers["Sec-Fetch-Site"] = "same-site"

    return headers


def _validate_response(response: httpx.Response) -> None:
    content_type = response.headers.get("content-type", "").lower()
    content_length = response.headers.get("content-length")

    try:
        size = int(content_length) if content_length else len(response.content)
    except Exception:
        size = len(response.content)

    if "json" in content_type and size > MAX_JSON_BYTES:
        raise RuntimeError("json_too_large")

    if "html" in content_type and size > MAX_HTML_BYTES:
        raise RuntimeError("html_too_large")

    if size > MAX_BINARY_BYTES:
        raise RuntimeError("binary_too_large")


def _validate_html_body(response: httpx.Response) -> None:
    content_type = response.headers.get("content-type", "").lower()

    if "html" not in content_type:
        return

    text = response.text or ""
    lowered = text.lower()

    if len(text.strip()) < MIN_HTML_TEXT_LENGTH:
        raise RuntimeError("empty_or_blocked_html")

    for token in _BLOCKED_HTML_TOKENS:
        if token in lowered:
            raise RuntimeError("blocked_html")


def _handle_compression(response: httpx.Response) -> None:
    encoding = response.headers.get("content-encoding", "").lower()

    if not encoding:
        return

    try:
        content = response.content

        if encoding == "gzip" and content[:2] == b"\x1f\x8b":
            content = gzip.decompress(content)
        elif encoding == "deflate":
            try:
                content = zlib.decompress(content)
            except zlib.error:
                content = zlib.decompress(content, -zlib.MAX_WBITS)
        elif encoding == "br":
            try:
                import brotli

                content = brotli.decompress(content)
            except Exception:
                pass

        response._content = content

        try:
            del response.headers["content-encoding"]
        except Exception:
            pass

    except Exception as exc:
        logger.debug("compression_fail error=%s", exc)


def _apply_cookie_updates(request_url: str, response: httpx.Response) -> None:
    try:
        values = response.headers.get_list("set-cookie")
    except Exception:
        values = []

    if not values:
        single = response.headers.get("set-cookie")
        if single:
            values = [single]

    for value in values:
        try:
            update_cookies(request_url, {"set-cookie": value})
        except Exception:
            continue


def _warm_host(target_url: str) -> None:
    host = _host(target_url)

    if not should_warm_host(host):
        return

    try:
        client = get_http_client(host)
        origin = _origin(target_url)
        warm_url = origin or target_url

        headers = _build_headers(
            warm_url,
            mode="document",
            method="GET",
            referer=warm_url,
        )

        cookie_header = get_cookie_header(warm_url)
        if cookie_header:
            headers["Cookie"] = cookie_header

        response = client.request(
            "GET",
            warm_url,
            headers=headers,
            timeout=WARMUP_TIMEOUT,
            follow_redirects=False,
        )
        response.read()
        _handle_compression(response)
        _apply_cookie_updates(str(response.url or warm_url), response)
    except Exception as exc:
        logger.debug("warm_host_failed url=%s error=%s", target_url, exc)


def _request_once(
    *,
    client: httpx.Client,
    url: str,
    method: str,
    merged_headers: dict[str, str],
    params: Optional[dict[str, Any]],
    data: Optional[Any],
    json: Optional[Any],
    timeout: float,
    max_redirects: int,
) -> httpx.Response:
    current_url = url
    history_urls: list[str] = []
    redirect_count = 0

    while True:
        response = client.request(
            method,
            current_url,
            headers=merged_headers,
            params=params,
            data=data,
            json=json,
            timeout=timeout,
            follow_redirects=False,
        )

        response.read()
        _handle_compression(response)
        _apply_cookie_updates(str(response.url or current_url), response)

        if 300 <= response.status_code < 400:
            location = response.headers.get("location")
            if not location:
                return response

            next_request = response.next_request
            next_url = str(next_request.url) if next_request else urljoin(current_url, location)

            decision = should_follow_redirect(
                next_url=next_url,
                redirect_count=redirect_count,
                history=history_urls,
            )

            if not decision.allow:
                raise httpx.HTTPError(decision.reason)

            history_urls = update_history(history_urls, next_url)
            current_url = next_url
            redirect_count += 1

            if redirect_count > max_redirects:
                raise httpx.HTTPError("too_many_redirects")

            continue

        return response


def _build_html_response(
    *,
    url: str,
    method: str,
    text: str,
    request_headers: Optional[dict[str, str]] = None,
    source: str = "fallback",
    attempt: int = 0,
) -> httpx.Response:
    request = httpx.Request(method, url, headers=request_headers)
    response = httpx.Response(
        status_code=200,
        headers={
            "content-type": "text/html; charset=utf-8",
            "x-fetch-source": source,
            "x-fetch-attempt": str(attempt),
        },
        content=text.encode("utf-8"),
        request=request,
    )
    return response


def _try_tls_fallback(
    *,
    url: str,
    host: str,
    attempt: int,
    method: str,
    merged_headers: dict[str, str],
    start: float,
    strategy_mode: str,
) -> Optional[httpx.Response]:
    if not _within_time_budget(start):
        return None

    try:
        logger.warning(
            "FETCH_TLS_FALLBACK url=%s host=%s attempt=%s",
            url,
            host,
            attempt,
        )

        html = fetch_impersonated(url)

        if html and len(html) > MIN_HTML_TEXT_LENGTH:
            response = _build_html_response(
                url=url,
                method=method,
                text=html,
                request_headers=merged_headers,
                source="impersonation",
                attempt=attempt,
            )

            logger.info(
                "FETCH_SUCCESS url=%s status=%s size=%s",
                url,
                response.status_code,
                len(response.content),
            )
            logger.debug(
                "fetch_ok host=%s mode=%s method=%s status=%s t=%ss via=impersonation",
                host,
                strategy_mode,
                method,
                response.status_code,
                round(time.monotonic() - start, 3),
            )

            return response

    except Exception as fallback_exc:
        logger.error(
            "FETCH_TLS_FALLBACK_FAILED url=%s host=%s error=%s",
            url,
            host,
            fallback_exc,
        )

    return None


def _try_browser_fallback(
    *,
    url: str,
    host: str,
    attempt: int,
    method: str,
    merged_headers: dict[str, str],
    start: float,
    strategy_mode: str,
    referer: Optional[str],
) -> Optional[httpx.Response]:
    if not _within_time_budget(start):
        return None

    if attempt > 1:
        return None

    try:
        logger.warning(
            "FETCH_BROWSER_FALLBACK url=%s host=%s attempt=%s",
            url,
            host,
            attempt,
        )

        html = fetch_with_browser(
            url,
            referer=referer,
        )

        if html and len(html) > MIN_HTML_TEXT_LENGTH:
            response = _build_html_response(
                url=url,
                method=method,
                text=html,
                request_headers=merged_headers,
                source="browser",
                attempt=attempt,
            )

            logger.info(
                "FETCH_SUCCESS url=%s status=%s size=%s",
                url,
                response.status_code,
                len(response.content),
            )
            logger.debug(
                "fetch_ok host=%s mode=%s method=%s status=%s t=%ss via=browser",
                host,
                strategy_mode,
                method,
                response.status_code,
                round(time.monotonic() - start, 3),
            )

            return response

    except Exception as browser_exc:
        logger.error(
            "FETCH_BROWSER_FALLBACK_FAILED url=%s host=%s error=%s",
            url,
            host,
            browser_exc,
        )

    return None


def fetch(
    url: str,
    *,
    method: str = "GET",
    mode: str = "document",
    headers: Optional[dict[str, str]] = None,
    params: Optional[dict[str, Any]] = None,
    data: Optional[Any] = None,
    json: Optional[Any] = None,
    timeout: Optional[float] = None,
    referer: Optional[str] = None,
) -> httpx.Response:
    host = _host(url)
    wait_for_domain(url)

    timeout = timeout or DEFAULT_TIMEOUT
    method = method.upper()
    policy = get_domain_policy(url)

    initial_strategy = build_request_strategy(
        url=url,
        mode=mode,
        method=method,
        referer=referer,
        policy=policy,
        attempt=1,
        previous_reason=None,
    )

    last_exc: Optional[Exception] = None
    last_reason: Optional[str] = None
    overall_start = time.monotonic()

    if initial_strategy.warm_host_first:
        _warm_host(url)

    for attempt in range(1, initial_strategy.max_attempts + 1):
        if not _within_time_budget(overall_start):
            raise RuntimeError("fetch_timeout_global")

        start = time.monotonic()

        strategy = build_request_strategy(
            url=url,
            mode=mode,
            method=method,
            referer=referer,
            policy=policy,
            attempt=attempt,
            previous_reason=last_reason,
        )

        client = get_http_client(host)

        merged_headers = _build_headers(
            url,
            mode=strategy.mode,
            method=method,
            referer=strategy.referer,
        )

        cookie_header = get_cookie_header(url)
        if cookie_header:
            merged_headers["Cookie"] = cookie_header

        if headers:
            for k, v in headers.items():
                if v is not None:
                    merged_headers[str(k)] = str(v)

        try:
            response = _request_once(
                client=client,
                url=url,
                method=method,
                merged_headers=merged_headers,
                params=params,
                data=data,
                json=json,
                timeout=timeout,
                max_redirects=min(MAX_REDIRECTS, strategy.max_redirects),
            )

            _validate_response(response)

            classification = classify_response(
                status_code=response.status_code,
                text=response.text,
                final_url=str(response.url or url),
                redirect_count=len(response.history),
            )

            if classification.is_blocked:
                last_reason = classification.reason

                if classification.penalize:
                    penalize_domain(url, seconds=policy.penalty_seconds)

                if classification.retryable and attempt < strategy.max_attempts:
                    logger.warning(
                        "FETCH_RETRY_BLOCKED url=%s host=%s attempt=%s reason=%s backoff=%s",
                        url,
                        host,
                        attempt,
                        classification.reason,
                        strategy.backoff_seconds,
                    )
                    time.sleep(strategy.backoff_seconds)
                    continue

                raise httpx.HTTPStatusError(
                    classification.reason,
                    request=response.request,
                    response=response,
                )

            _validate_html_body(response)

            logger.info(
                "FETCH_SUCCESS url=%s status=%s size=%s",
                url,
                response.status_code,
                len(response.content),
            )
            logger.debug(
                "fetch_ok host=%s mode=%s method=%s status=%s t=%ss via=httpx",
                host,
                strategy.mode,
                method,
                response.status_code,
                round(time.monotonic() - start, 3),
            )

            return response

        except Exception as exc:
            last_exc = exc
            classification = classify_exception(exc)
            last_reason = classification.reason

            logger.warning(
                "FETCH_FAILED url=%s host=%s attempt=%s error=%s reason=%s",
                url,
                host,
                attempt,
                exc,
                classification.reason,
            )

            if classification.penalize:
                penalize_domain(url, seconds=policy.penalty_seconds)

            if isinstance(
                exc,
                (
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                    httpx.ReadTimeout,
                    httpx.ConnectTimeout,
                    httpx.ConnectError,
                ),
            ):
                reset_http_client()

            if not _within_time_budget(overall_start):
                raise RuntimeError("fetch_timeout_global") from exc

            if last_reason in ("hard_403", "blocked_html", "bot_challenge"):
                tls_response = _try_tls_fallback(
                    url=url,
                    host=host,
                    attempt=attempt,
                    method=method,
                    merged_headers=merged_headers,
                    start=overall_start,
                    strategy_mode=strategy.mode,
                )
                if tls_response is not None:
                    return tls_response

            if last_reason in ("blocked_html", "bot_challenge", "empty_or_blocked_html", "captcha"):
                browser_response = _try_browser_fallback(
                    url=url,
                    host=host,
                    attempt=attempt,
                    method=method,
                    merged_headers=merged_headers,
                    start=overall_start,
                    strategy_mode=strategy.mode,
                    referer=strategy.referer,
                )
                if browser_response is not None:
                    return browser_response

            if (
                attempt >= strategy.max_attempts
                or not classification.retryable
                or classification.skip_same_strategy
            ):
                logger.warning(
                    "fetch_fail host=%s mode=%s method=%s url=%s err=%s reason=%s",
                    host,
                    strategy.mode,
                    method,
                    url,
                    exc,
                    classification.reason,
                )
                raise

            if not _within_time_budget(overall_start):
                raise RuntimeError("fetch_timeout_global") from exc

            time.sleep(strategy.backoff_seconds)

    if last_exc:
        raise last_exc

    raise RuntimeError(f"fetch_failed url={url}")