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

import os
import subprocess

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/sentry-test", dependencies=[Depends(require_api_key)])
def sentry_test() -> None:
    raise RuntimeError(
        "CRAVE debug/sentry-test: deliberate test error, safe to ignore — "
        "confirms this event reached Sentry."
    )


def _git_commit_fallback() -> str | None:
    # Only reached if RAILWAY_GIT_COMMIT_SHA isn't set (e.g. running
    # locally, not on Railway) -- a production container built without
    # the .git directory would just make this raise, which is caught.
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "HEAD"],
                cwd=os.path.dirname(os.path.abspath(__file__)),
                stderr=subprocess.DEVNULL,
                timeout=2,
            )
            .decode()
            .strip()
        )
    except Exception:
        return None


@router.get("/version")
def version() -> dict:
    """
    Answers one question directly, instead of asking someone to trust an
    assurance: "is the commit I think is deployed actually the commit
    that's running?" Railway sets RAILWAY_GIT_COMMIT_SHA on every
    GitHub-integration deploy automatically -- compare the "commit"
    field here against `git rev-parse HEAD` on the branch tip locally
    (or the SHA shown in the Railway dashboard's deployment list) to
    settle it in one request, no dashboard digging required.
    """
    commit = os.environ.get("RAILWAY_GIT_COMMIT_SHA") or _git_commit_fallback()
    return {
        "commit": commit,
        "commit_short": commit[:12] if commit else None,
        "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        or os.environ.get("RAILWAY_ENVIRONMENT"),
        "railway_deployment_id": os.environ.get("RAILWAY_DEPLOYMENT_ID"),
    }
