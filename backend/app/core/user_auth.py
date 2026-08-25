"""
Supabase JWT verification — the fix for CRAVE's core IDOR vulnerability.

Before this file existed, every user-scoped route (saves, hitlist) accepted
`user_id` as a plain client-supplied query/body param with zero verification.
Anyone with the API key (which itself ships inside the public app bundle —
EXPO_PUBLIC_API_KEY — so it's not really secret either) could read, create, or
delete *any other user's* saved places just by passing their UUID.

Usage:
    from app.core.user_auth import get_current_user_id

    @router.get("/saves")
    def list_saves(user_id: str = Depends(get_current_user_id), ...): ...

The frontend must send the Supabase session's access token as:
    Authorization: Bearer <access_token>
(supabase-js exposes this as `(await supabase.auth.getSession()).data.session.access_token`)

Configuration:
    SUPABASE_URL — the project's URL (Project Settings > API > Project URL),
    same value as the frontend's EXPO_PUBLIC_SUPABASE_URL. Required in prod.
    app/main.py refuses to start in prod without it set, so the dev bypass
    below can never silently apply in production.

    Verification fetches the project's public signing keys from
    <SUPABASE_URL>/auth/v1/.well-known/jwks.json and checks the token's
    signature against them, rather than decoding against a shared secret.
    Supabase signs access tokens with an asymmetric key (ES256 as of this
    writing) — there is no separate static "JWT secret" to configure for a
    project on this system, and one would be structurally unable to verify
    an ES256-signed token anyway (wrong algorithm family entirely, not just
    a wrong value). The public key is, by design, safe to fetch over the
    network on every verifying process — it can't be used to forge tokens.

Dev bypass:
    If SUPABASE_URL is unset and APP_ENV != "prod", an unauthenticated
    request is treated as a fixed "dev-user" id, so local development without
    a real Supabase session still works. Every request without a real token
    resolves to the SAME id in this mode — it is not per-device, just a
    convenience so `/saves` etc. are exercisable locally.
"""
from __future__ import annotations

import logging
from typing import Optional

import jwt
from fastapi import Header, HTTPException
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientError

from app.config.settings import settings

logger = logging.getLogger(__name__)

_DEV_FALLBACK_USER_ID = "dev-user"

# Supabase issues access tokens with this audience claim for authenticated users.
_EXPECTED_AUDIENCE = "authenticated"

# Supabase's asymmetric-key projects currently sign with ES256; RS256 is
# accepted too since Supabase supports either key type depending on project
# configuration. Deliberately excludes HS256 — a shared-secret algorithm has
# no business being verifiable from a *public* JWKS in the first place.
_ALLOWED_ALGORITHMS = ["ES256", "RS256"]

# One client per process, reused across requests. PyJWKClient caches the
# fetched keyset in memory and only refetches when it sees an unknown `kid`
# (e.g. after Supabase rotates keys), so this doesn't hit the network on
# every call.
_jwks_client: Optional[PyJWKClient] = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_keys=True)
    return _jwks_client


def get_current_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    """
    FastAPI dependency. Verifies the bearer token and returns the Supabase
    auth user id (`sub` claim). Raises 401 on anything else.
    """
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        if not settings.supabase_url and not settings.is_prod:
            logger.debug("auth_dev_bypass no_bearer_token_dev_mode")
            return _DEV_FALLBACK_USER_ID
        raise HTTPException(status_code=401, detail="Missing bearer token")

    if not settings.supabase_url:
        # Unreachable in prod — app/main.py's startup check hard-fails boot
        # if SUPABASE_URL is unset while APP_ENV=prod. If you're seeing
        # this, the startup guard was bypassed or removed.
        logger.error("auth_misconfigured supabase_url_unset")
        raise HTTPException(status_code=500, detail="Auth not configured")

    try:
        signing_key = _get_jwks_client().get_signing_key_from_jwt(token)
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=_ALLOWED_ALGORITHMS,
            audience=_EXPECTED_AUDIENCE,
        )
    except PyJWKClientError as exc:
        logger.warning("auth_invalid_token jwks_lookup_failed error=%s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as exc:
        logger.warning("auth_invalid_token error=%s", exc)
        raise HTTPException(status_code=401, detail="Invalid token")

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    return str(user_id)


def get_current_user_id_optional(authorization: Optional[str] = Header(default=None)) -> Optional[str]:
    """
    Same verification as get_current_user_id, but for routes that behave
    differently for a signed-in viewer without *requiring* sign-in (e.g. a
    public profile that also shows a "Match Score" when the viewer happens
    to be logged in). Returns None instead of raising on a missing or
    invalid token -- callers must treat None as "anonymous", not as an
    error to surface.
    """
    try:
        return get_current_user_id(authorization=authorization)
    except HTTPException:
        return None
