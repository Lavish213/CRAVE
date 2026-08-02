# app/services/profile/profile_service.py
from __future__ import annotations

import re
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models.user_profile import UserProfile

_USERNAME_RE = re.compile(r"^[a-z0-9_]{3,20}$")


def _normalize_username(username: str) -> str:
    return (username or "").strip().lower()


def is_valid_username(username: str) -> bool:
    return bool(_USERNAME_RE.match(_normalize_username(username)))


def username_available(db: Session, username: str) -> bool:
    normalized = _normalize_username(username)
    if not is_valid_username(normalized):
        return False
    existing = db.query(UserProfile.id).filter(UserProfile.username == normalized).first()
    return existing is None


def create_profile(
    db: Session,
    *,
    user_id: str,
    username: str,
    display_name: Optional[str] = None,
) -> UserProfile:
    normalized = _normalize_username(username)
    if not is_valid_username(normalized):
        raise ValueError(
            "username must be 3-20 characters, lowercase letters/numbers/underscore only"
        )

    if db.query(UserProfile).filter(UserProfile.id == user_id).first():
        raise ValueError("profile already exists")

    if db.query(UserProfile.id).filter(UserProfile.username == normalized).first():
        raise ValueError("username already taken")

    profile = UserProfile(
        id=user_id,
        username=normalized,
        display_name=(display_name or "").strip() or None,
    )
    db.add(profile)
    db.commit()
    return profile


def get_profile(db: Session, user_id: str) -> Optional[UserProfile]:
    return db.query(UserProfile).filter(UserProfile.id == user_id).one_or_none()


def update_profile(
    db: Session,
    *,
    user_id: str,
    display_name: Optional[str] = None,
    bio: Optional[str] = None,
    avatar_url: Optional[str] = None,
    is_public: Optional[bool] = None,
) -> UserProfile:
    profile = get_profile(db, user_id)
    if not profile:
        raise ValueError("profile not found")

    if display_name is not None:
        profile.display_name = display_name.strip() or None
    if bio is not None:
        profile.bio = bio.strip() or None
    if avatar_url is not None:
        profile.avatar_url = avatar_url.strip() or None
    if is_public is not None:
        profile.is_public = is_public

    db.commit()
    return profile
