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
    SUPABASE_JWT_SECRET — from the Supabase dashboard:
    Project Settings > API > JWT Settings > JWT Secret.
    Required in prod. app/main.py refuses to start in prod without it set,
    so the dev bypass below can never silently apply in production.

Dev bypass:
    If SUPABASE_JWT_SECRET is unset and APP_ENV != "prod", an unauthenticated
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

from app.config.settings import settings

logger = logging.getLogger(__name__)

_DEV_FALLBACK_USER_ID = "dev-user"

# Supabase issues access tokens with this audience claim for authenticated users.
_EXPECTED_AUDIENCE = "authenticated"


def get_current_user_id(authorization: Optional[str] = Header(default=None)) -> str:
    """
    FastAPI dependency. Verifies the bearer token and returns the Supabase
    auth user id (`sub` claim). Raises 401 on anything else.
    """
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()

    if not token:
        if not settings.supabase_jwt_secret and not settings.is_prod:
            logger.debug("auth_dev_bypass no_bearer_token_dev_mode")
            return _DEV_FALLBACK_USER_ID
        raise HTTPException(status_code=401, detail="Missing bearer token")

    if not settings.supabase_jwt_secret:
        # Unreachable in prod — app/main.py's startup check hard-fails boot
        # if SUPABASE_JWT_SECRET is unset while APP_ENV=prod. If you're
        # seeing this, the startup guard was bypassed or removed.
        logger.error("auth_misconfigured supabase_jwt_secret_unset")
        raise HTTPException(status_code=500, detail="Auth not configured")

    try:
        payload = jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience=_EXPECTED_AUDIENCE,
        )
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
