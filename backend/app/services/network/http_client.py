from __future__ import annotations

import atexit
import logging
import os
import ssl
import threading
import time
from typing import Optional

import certifi
import httpx
import truststore

from app.services.network.proxy_pool import get_proxy
from app.services.network.session_identity import get_identity


truststore.inject_into_ssl()

logger = logging.getLogger(__name__)


MAX_CONNECTIONS = int(os.getenv("HTTP_MAX_CONNECTIONS", "150"))
MAX_KEEPALIVE_CONNECTIONS = int(os.getenv("HTTP_MAX_KEEPALIVE_CONNECTIONS", "60"))
KEEPALIVE_EXPIRY_SECONDS = float(os.getenv("HTTP_KEEPALIVE_EXPIRY_SECONDS", "60"))

CONNECT_TIMEOUT_SECONDS = float(os.getenv("HTTP_CONNECT_TIMEOUT_SECONDS", "8"))
READ_TIMEOUT_SECONDS = float(os.getenv("HTTP_READ_TIMEOUT_SECONDS", "20"))
WRITE_TIMEOUT_SECONDS = float(os.getenv("HTTP_WRITE_TIMEOUT_SECONDS", "15"))
POOL_TIMEOUT_SECONDS = float(os.getenv("HTTP_POOL_TIMEOUT_SECONDS", "8"))

TRANSPORT_RETRIES = int(os.getenv("HTTP_TRANSPORT_RETRIES", "2"))
REQUEST_RESET_INTERVAL = int(os.getenv("HTTP_REQUEST_RESET_INTERVAL", "500"))

DNS_CACHE_TTL_SECONDS = int(os.getenv("HTTP_DNS_CACHE_TTL_SECONDS", "300"))


_HTTP_CLIENT: Optional[httpx.Client] = None
_HTTP_CLIENT_PROXY_KEY: Optional[str] = None
_CLIENT_LOCK = threading.Lock()
_CLIENT_REGISTERED = False
_REQUEST_COUNT = 0

_DNS_CACHE: dict[str, float] = {}


def _dns_cache_cleanup() -> None:
    now = time.time()
    expired = [
        hostname
        for hostname, ts in _DNS_CACHE.items()
        if now - ts > DNS_CACHE_TTL_SECONDS
    ]

    for hostname in expired:
        _DNS_CACHE.pop(hostname, None)


def _build_ssl_context() -> ssl.SSLContext:
    try:
        ctx = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        logger.debug("ssl_context_source=truststore")
    except Exception:
        logger.debug("truststore_ssl_failed_fallback_certifi")

        try:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.load_verify_locations(certifi.where())
            logger.debug("ssl_context_source=certifi")
        except Exception:
            logger.debug("certifi_ssl_failed_fallback_default")
            ctx = ssl.create_default_context()

    env_cert_file = os.getenv("SSL_CERT_FILE")

    if env_cert_file:
        try:
            ctx.load_verify_locations(env_cert_file)
            logger.debug("ssl_context_env_cert_loaded path=%s", env_cert_file)
        except Exception as exc:
            logger.warning(
                "ssl_context_env_cert_failed path=%s error=%s",
                env_cert_file,
                exc,
            )

    try:
        ctx.load_verify_locations(certifi.where())
        logger.debug("ssl_context_certifi_loaded path=%s", certifi.where())
    except Exception as exc:
        logger.warning("ssl_context_certifi_load_failed error=%s", exc)

    ctx.check_hostname = True
    ctx.verify_mode = ssl.CERT_REQUIRED
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2

    return ctx


def _build_limits() -> httpx.Limits:
    return httpx.Limits(
        max_connections=MAX_CONNECTIONS,
        max_keepalive_connections=MAX_KEEPALIVE_CONNECTIONS,
        keepalive_expiry=KEEPALIVE_EXPIRY_SECONDS,
    )


def _build_timeout() -> httpx.Timeout:
    return httpx.Timeout(
        connect=CONNECT_TIMEOUT_SECONDS,
        read=READ_TIMEOUT_SECONDS,
        write=WRITE_TIMEOUT_SECONDS,
        pool=POOL_TIMEOUT_SECONDS,
    )


def _build_headers(user_agent: Optional[str] = None) -> dict[str, str]:
    ua = user_agent or (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/123.0.0.0 Safari/537.36"
    )

    return {
        "User-Agent": ua,
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;"
            "q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "DNT": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "sec-ch-ua": '"Google Chrome";v="123", "Chromium";v="123", "Not:A-Brand";v="24"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"macOS"',
    }


def _build_transport(ssl_context: ssl.SSLContext, proxy: Optional[str]) -> httpx.BaseTransport:
    if proxy:
        logger.debug("http_transport_proxy_enabled proxy=%s", proxy)
        return httpx.HTTPTransport(
            verify=ssl_context,
            retries=TRANSPORT_RETRIES,
            proxy=proxy,
        )

    return httpx.HTTPTransport(
        verify=ssl_context,
        retries=TRANSPORT_RETRIES,
    )


def _create_client(*, host: Optional[str] = None, proxy: Optional[str] = None) -> httpx.Client:
    ssl_context = _build_ssl_context()
    transport = _build_transport(ssl_context, proxy)

    identity_ua: Optional[str] = None
    if host:
        try:
            identity_ua = get_identity(host).user_agent
        except Exception as exc:
            logger.debug("session_identity_lookup_failed host=%s error=%s", host, exc)

    client = httpx.Client(
        http2=True,
        verify=ssl_context,
        limits=_build_limits(),
        timeout=_build_timeout(),
        headers=_build_headers(identity_ua),
        transport=transport,
        follow_redirects=False,
        max_redirects=10,
        trust_env=True,
    )

    logger.debug(
        "http_client_created host=%s proxy=%s max_connections=%s max_keepalive=%s "
        "keepalive_expiry=%s connect_timeout=%s read_timeout=%s write_timeout=%s "
        "pool_timeout=%s retries=%s",
        host,
        proxy,
        MAX_CONNECTIONS,
        MAX_KEEPALIVE_CONNECTIONS,
        KEEPALIVE_EXPIRY_SECONDS,
        CONNECT_TIMEOUT_SECONDS,
        READ_TIMEOUT_SECONDS,
        WRITE_TIMEOUT_SECONDS,
        POOL_TIMEOUT_SECONDS,
        TRANSPORT_RETRIES,
    )

    return client


def _client_is_alive(client: httpx.Client) -> bool:
    try:
        return not client.is_closed
    except Exception:
        return False


def _safe_close_client() -> None:
    global _HTTP_CLIENT
    global _HTTP_CLIENT_PROXY_KEY

    try:
        if _HTTP_CLIENT:
            _HTTP_CLIENT.close()
            logger.debug("http_client_closed")
    except Exception:
        pass
    finally:
        _HTTP_CLIENT = None
        _HTTP_CLIENT_PROXY_KEY = None


def _should_rotate_client(proxy_key: Optional[str]) -> bool:
    global _HTTP_CLIENT
    global _HTTP_CLIENT_PROXY_KEY
    global _REQUEST_COUNT

    if not _HTTP_CLIENT or not _client_is_alive(_HTTP_CLIENT):
        return True

    if proxy_key != _HTTP_CLIENT_PROXY_KEY:
        logger.debug(
            "http_client_proxy_changed old=%s new=%s",
            _HTTP_CLIENT_PROXY_KEY,
            proxy_key,
        )
        return True

    if REQUEST_RESET_INTERVAL > 0 and _REQUEST_COUNT > 0 and _REQUEST_COUNT % REQUEST_RESET_INTERVAL == 0:
        logger.debug(
            "http_client_periodic_reset request_count=%s interval=%s",
            _REQUEST_COUNT,
            REQUEST_RESET_INTERVAL,
        )
        return True

    return False


def get_http_client(host: Optional[str] = None) -> httpx.Client:
    global _HTTP_CLIENT
    global _HTTP_CLIENT_PROXY_KEY
    global _CLIENT_REGISTERED
    global _REQUEST_COUNT

    proxy = None
    try:
        proxy = get_proxy()
    except Exception as exc:
        logger.debug("proxy_pool_lookup_failed error=%s", exc)

    proxy_key = proxy or "__direct__"

    if _HTTP_CLIENT and _client_is_alive(_HTTP_CLIENT) and not _should_rotate_client(proxy_key):
        with _CLIENT_LOCK:
            if _HTTP_CLIENT and _client_is_alive(_HTTP_CLIENT) and not _should_rotate_client(proxy_key):
                _REQUEST_COUNT += 1
                return _HTTP_CLIENT

    with _CLIENT_LOCK:
        if _HTTP_CLIENT and _client_is_alive(_HTTP_CLIENT) and not _should_rotate_client(proxy_key):
            _REQUEST_COUNT += 1
            return _HTTP_CLIENT

        if _HTTP_CLIENT:
            try:
                _HTTP_CLIENT.close()
            except Exception:
                pass
            finally:
                _HTTP_CLIENT = None
                _HTTP_CLIENT_PROXY_KEY = None

        try:
            _dns_cache_cleanup()
            client = _create_client(host=host, proxy=proxy)
        except Exception as exc:
            logger.exception("http_client_init_failed host=%s proxy=%s error=%s", host, proxy, exc)
            raise

        _HTTP_CLIENT = client
        _HTTP_CLIENT_PROXY_KEY = proxy_key
        _REQUEST_COUNT += 1

        if not _CLIENT_REGISTERED:
            try:
                atexit.register(_safe_close_client)
                _CLIENT_REGISTERED = True
            except Exception:
                pass

        logger.debug("http_client_initialized host=%s proxy=%s", host, proxy)

        return _HTTP_CLIENT


def reset_http_client() -> None:
    global _HTTP_CLIENT
    global _HTTP_CLIENT_PROXY_KEY
    global _REQUEST_COUNT

    with _CLIENT_LOCK:
        if _HTTP_CLIENT:
            try:
                _HTTP_CLIENT.close()
            except Exception:
                pass

        _HTTP_CLIENT = None
        _HTTP_CLIENT_PROXY_KEY = None
        _REQUEST_COUNT = 0

        logger.warning("http_client_reset")


def close_http_client() -> None:
    reset_http_client()