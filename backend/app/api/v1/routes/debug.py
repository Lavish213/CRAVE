"""
Manual, one-shot verification that SENTRY_DSN is actually wired end-to-end
in whatever environment this is running in. Confirming the env var is *set*
isn't the same as confirming Sentry actually receives events from it — this
endpoint deliberately raises so app/main.py's global_exception_handler runs
for real and calls sentry_sdk.capture_exception, then you check the Sentry
project dashboard for the event.

Gated behind require_api_key (same mechanism every other write/admin-ish
endpoint uses) since it's a deliberate 500 — not something that should be
free for anyone to hit repeatedly.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/sentry-test", dependencies=[Depends(require_api_key)])
def sentry_test() -> None:
    raise RuntimeError(
        "CRAVE debug/sentry-test: deliberate test error, safe to ignore — "
        "confirms this event reached Sentry."
    )
