"""
Shared trust-tier allowlists: admin (full moderation access) and trusted
contributor (photo/menu-photo uploads skip the mandatory review hold that
otherwise applies to every other signed-in user — see
app/services/images/upload_moderation.py).

Deliberately the crudest possible mechanism, matching the precedent
moderation.py already set for ADMIN_USER_IDS: there is no role system in
this app, and building one is a bigger change than either feature
warrants. Both fail closed — an unset allowlist means nobody gets the
privilege, not everybody.
"""
from __future__ import annotations

import os
from typing import Optional


def _ids_from_env(var_name: str) -> set[str]:
    raw = os.getenv(var_name, "")
    return {part.strip() for part in raw.split(",") if part.strip()}


def admin_ids() -> set[str]:
    return _ids_from_env("ADMIN_USER_IDS")


def trusted_contributor_ids() -> set[str]:
    return _ids_from_env("TRUSTED_CONTRIBUTOR_USER_IDS")


def is_admin(user_id: Optional[str]) -> bool:
    return bool(user_id) and user_id in admin_ids()


def is_trusted_contributor(user_id: Optional[str]) -> bool:
    """
    True for admins and for accounts explicitly allow-listed as trusted
    contributors (staff, verified local partners, influencers). Everyone
    else's photo/menu-photo uploads are held for human review regardless
    of what the automated quality/safety pipeline would otherwise decide —
    that pipeline still runs for them exactly as it does for anyone else,
    it just can no longer be the sole gate for going live.
    """
    if not user_id:
        return False
    return user_id in admin_ids() or user_id in trusted_contributor_ids()
