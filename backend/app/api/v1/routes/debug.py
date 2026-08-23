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
from pathlib import Path

from fastapi import APIRouter, Depends

from app.core.auth import require_api_key

router = APIRouter(prefix="/debug", tags=["debug"])


@router.get("/sentry-test", dependencies=[Depends(require_api_key)])
def sentry_test() -> None:
    raise RuntimeError(
        "CRAVE debug/sentry-test: deliberate test error, safe to ignore — "
        "confirms this event reached Sentry."
    )


# backend/GIT_COMMIT.txt -- four levels up from this file
# (routes -> v1 -> api -> app -> backend). Not committed (see .gitignore);
# regenerated fresh right before each deploy. This is the primary source
# for /version: confirmed live that `railway up` (uploading a local
# directory, not a GitHub-connected clone) sets neither
# RAILWAY_GIT_COMMIT_SHA nor an in-container .git directory, so both of
# those were dead ends for this project's actual deploy method.
_GIT_COMMIT_FILE = Path(__file__).resolve().parents[4] / "GIT_COMMIT.txt"


def _git_commit_from_file() -> str | None:
    try:
        return _GIT_COMMIT_FILE.read_text().strip() or None
    except Exception:
        return None


def _git_commit_fallback() -> str | None:
    # Last resort for a plain local run where .git genuinely is present
    # (e.g. `uvicorn app.main:app` from a dev checkout) -- not expected
    # to resolve anything in the deployed container, see above.
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
    that's running?" Reads backend/GIT_COMMIT.txt (written by
    `git rev-parse HEAD > backend/GIT_COMMIT.txt` right before deploying
    -- see the project's deploy instructions) first, since this
    project's actual deploy method (`railway up` from a local checkout)
    doesn't populate RAILWAY_GIT_COMMIT_SHA or carry .git into the
    container -- both kept as fallbacks in case the deploy method ever
    changes to a GitHub-connected one.
    """
    commit = (
        _git_commit_from_file()
        or os.environ.get("RAILWAY_GIT_COMMIT_SHA")
        or _git_commit_fallback()
    )
    return {
        "commit": commit,
        "commit_short": commit[:12] if commit else None,
        "railway_environment": os.environ.get("RAILWAY_ENVIRONMENT_NAME")
        or os.environ.get("RAILWAY_ENVIRONMENT"),
        "railway_deployment_id": os.environ.get("RAILWAY_DEPLOYMENT_ID"),
    }
