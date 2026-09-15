"""Production Supabase-auth smoke gate.

This script verifies the backend's auth-critical Supabase configuration without
printing credentials. It is meant to be run after provider setup/deploy, e.g.:

    APP_ENV=prod SUPABASE_URL=https://... \
    SUPABASE_SMOKE_ACCESS_TOKEN=<real user access token> \
    python scripts/smoke_supabase_auth.py --require-token

Provider setup itself still happens in Supabase's dashboard/CLI. This script is
the backend gate that proves the deployed service can verify the resulting JWTs.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config.settings import settings
from app.core import user_auth
from app.core.user_auth import get_current_user_id


def _jwks_url() -> str:
    return f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"


def _validate_supabase_url() -> list[str]:
    errors: list[str] = []
    value = (settings.supabase_url or "").strip()
    if not value:
        errors.append("SUPABASE_URL is not set")
        return errors
    parsed = urlparse(value)
    if parsed.scheme != "https":
        errors.append("SUPABASE_URL must be https")
    if not parsed.netloc:
        errors.append("SUPABASE_URL must include a host")
    return errors


def _fetch_jwks(timeout: float) -> dict:
    with urllib.request.urlopen(_jwks_url(), timeout=timeout) as response:  # nosec B310 - operator-provided Supabase URL
        return json.loads(response.read().decode("utf-8"))


def run_smoke(*, token_env: str, require_token: bool, skip_jwks_fetch: bool, timeout: float) -> tuple[int, dict]:
    errors = _validate_supabase_url()
    result: dict = {
        "app_env": settings.app_env,
        "is_prod": settings.is_prod,
        "supabase_url_configured": bool(settings.supabase_url),
        "jwks_url": _jwks_url() if settings.supabase_url else None,
        "jwks_fetch": "skipped" if skip_jwks_fetch else "not_run",
        "token_env": token_env,
        "token_verified": False,
    }
    if errors:
        result["errors"] = errors
        return 2, result

    if not skip_jwks_fetch:
        try:
            jwks = _fetch_jwks(timeout)
            key_count = len(jwks.get("keys") or [])
            result["jwks_fetch"] = "ok"
            result["jwks_key_count"] = key_count
            if key_count < 1:
                result.setdefault("errors", []).append("Supabase JWKS returned no keys")
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
            result["jwks_fetch"] = "failed"
            result.setdefault("errors", []).append(f"JWKS fetch failed: {type(exc).__name__}")

    token = os.environ.get(token_env, "").strip()
    if not token:
        result["token_present"] = False
        if require_token:
            result.setdefault("errors", []).append(f"{token_env} is required")
        return (2 if result.get("errors") else 0), result

    result["token_present"] = True
    try:
        # Ensure tests or repeated smoke runs don't reuse a previous project's
        # cached JWKS client after env changes.
        user_auth._jwks_client = None
        user_id = get_current_user_id(authorization=f"Bearer {token}")
        result["token_verified"] = True
        result["user_id_suffix"] = user_id[-8:]
    except Exception as exc:  # noqa: BLE001 - operator-facing smoke summary
        result.setdefault("errors", []).append(f"Token verification failed: {type(exc).__name__}")

    return (2 if result.get("errors") else 0), result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--token-env", default="SUPABASE_SMOKE_ACCESS_TOKEN")
    parser.add_argument("--require-token", action="store_true")
    parser.add_argument("--skip-jwks-fetch", action="store_true")
    parser.add_argument("--timeout", type=float, default=5.0)
    args = parser.parse_args(argv)

    code, result = run_smoke(
        token_env=args.token_env,
        require_token=args.require_token,
        skip_jwks_fetch=args.skip_jwks_fetch,
        timeout=args.timeout,
    )
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
