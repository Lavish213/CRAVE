# app/services/account/account_deletion_service.py
"""
Account deletion — required for App Store review (Guideline 5.1.1(v)):
any app that supports account creation must let the user initiate account
deletion from inside the app, not just delete their profile data.

Two halves, both necessary:
1. App-side data (UserProfile, UserFollow, UserBlock rows) — this repo's
   own tables.
2. The actual Supabase Auth identity (email/password credential) — this
   app never owned auth, Supabase does (see app/core/user_auth.py's
   module docstring), so "delete the account" means calling Supabase's
   Admin API to delete the auth user, not just clearing app data. Without
   this half, someone who "deleted their account" could still log back in
   with the same email/password — which doesn't satisfy Apple's
   requirement and defeats the point for the user too.

Deliberately scoped: does NOT sweep every table that stores this user's
id (place claims, submitted photos, craves/rankings, moderation records).
Those are left in place, same as most social apps handle it — a deleted
account's past public contributions can remain, just no longer tied to a
reachable profile/credential. A full data-retention sweep is real,
separate follow-up work, not silently skipped — see CRAVE_REMAINING_WORK.md.
"""
from __future__ import annotations

import logging
import os
from typing import Dict

import requests
from sqlalchemy.orm import Session

from app.db.models.user_profile import UserProfile
from app.db.models.user_follow import UserFollow
from app.db.models.user_block import UserBlock

logger = logging.getLogger(__name__)

_TIMEOUT = 15


def _delete_supabase_auth_user(user_id: str) -> bool:
    """
    Calls Supabase's Admin API to delete the auth identity itself. Returns
    False (never raises) on any failure — missing config, network error,
    non-2xx — so a Supabase-side hiccup can't leave the caller with a
    half-deleted app profile and no way to know what happened; the caller
    surfaces this in its response instead.
    """
    base_url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "").strip()

    if not base_url or not service_key:
        logger.error(
            "account_deletion_supabase_not_configured user_id=%s — "
            "SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY unset, auth identity "
            "NOT deleted, only app-side data was removed",
            user_id,
        )
        return False

    try:
        resp = requests.delete(
            f"{base_url}/auth/v1/admin/users/{user_id}",
            headers={
                "apikey": service_key,
                "Authorization": f"Bearer {service_key}",
            },
            timeout=_TIMEOUT,
        )
    except Exception as exc:
        logger.error(
            "account_deletion_supabase_request_failed user_id=%s error=%s",
            user_id, exc,
        )
        return False

    if resp.status_code not in (200, 204):
        logger.error(
            "account_deletion_supabase_upstream_error user_id=%s status=%s",
            user_id, resp.status_code,
        )
        return False

    return True


def delete_account(db: Session, user_id: str) -> Dict[str, bool]:
    """
    Deletes this user's app-side profile/social data and their Supabase
    auth identity. Idempotent — calling this on an already-deleted user_id
    just deletes nothing on the app side and reports supabase_account_
    deleted based on whatever Supabase itself returns.
    """
    profile_deleted = (
        db.query(UserProfile).filter(UserProfile.id == user_id).delete(
            synchronize_session=False
        )
        > 0
    )

    db.query(UserFollow).filter(
        (UserFollow.follower_id == user_id) | (UserFollow.followee_id == user_id)
    ).delete(synchronize_session=False)

    db.query(UserBlock).filter(
        (UserBlock.blocker_id == user_id) | (UserBlock.blocked_id == user_id)
    ).delete(synchronize_session=False)

    db.commit()

    supabase_account_deleted = _delete_supabase_auth_user(user_id)

    logger.info(
        "account_deletion_complete user_id=%s profile_deleted=%s supabase_account_deleted=%s",
        user_id, profile_deleted, supabase_account_deleted,
    )

    return {
        "profile_deleted": profile_deleted,
        "supabase_account_deleted": supabase_account_deleted,
    }
