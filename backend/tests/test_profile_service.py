"""
Coverage for app.services.profile.profile_service — the profile layer
that didn't exist before this session: Supabase owns auth, but has no
notion of username/avatar/bio, and every other table just stores a bare
user_id string with nothing to show for it.
"""
from __future__ import annotations

import uuid

import pytest

from app.db.session import SessionLocal
from app.db.models.user_profile import UserProfile
from app.services.profile import profile_service


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def user_id():
    uid = f"profile-test-{uuid.uuid4().hex[:8]}"
    yield uid


@pytest.fixture(autouse=True)
def _cleanup(db):
    yield
    db.query(UserProfile).filter(UserProfile.id.like("profile-test-%")).delete(
        synchronize_session=False
    )
    db.commit()


def test_valid_usernames_accepted():
    assert profile_service.is_valid_username("alice_123")
    assert profile_service.is_valid_username("ABC")  # normalized to lowercase


def test_invalid_usernames_rejected():
    assert not profile_service.is_valid_username("ab")  # too short
    assert not profile_service.is_valid_username("a" * 21)  # too long
    assert not profile_service.is_valid_username("has space")
    assert not profile_service.is_valid_username("has-dash")
    assert not profile_service.is_valid_username("")


def test_create_profile_succeeds(db, user_id):
    profile = profile_service.create_profile(db, user_id=user_id, username="AliceEats")
    assert profile.id == user_id
    assert profile.username == "aliceeats"  # normalized
    assert profile.is_public is True


def test_create_profile_rejects_invalid_username(db, user_id):
    with pytest.raises(ValueError):
        profile_service.create_profile(db, user_id=user_id, username="x")


def test_create_profile_rejects_duplicate_username(db, user_id):
    profile_service.create_profile(db, user_id=user_id, username="tacotuesday")

    other_user = f"profile-test-{uuid.uuid4().hex[:8]}"
    with pytest.raises(ValueError, match="already taken"):
        profile_service.create_profile(db, user_id=other_user, username="TacoTuesday")


def test_create_profile_rejects_second_profile_for_same_user(db, user_id):
    profile_service.create_profile(db, user_id=user_id, username="firstname")
    with pytest.raises(ValueError, match="already exists"):
        profile_service.create_profile(db, user_id=user_id, username="secondname")


def test_username_available_reflects_existing_rows(db, user_id):
    assert profile_service.username_available(db, "freshname") is True
    profile_service.create_profile(db, user_id=user_id, username="freshname")
    assert profile_service.username_available(db, "freshname") is False
    assert profile_service.username_available(db, "FreshName") is False  # case-insensitive


def test_update_profile_updates_fields(db, user_id):
    profile_service.create_profile(db, user_id=user_id, username="editme")
    updated = profile_service.update_profile(
        db, user_id=user_id, display_name="Alice", bio="foodie", is_public=False,
    )
    assert updated.display_name == "Alice"
    assert updated.bio == "foodie"
    assert updated.is_public is False


def test_update_profile_missing_raises(db):
    with pytest.raises(ValueError, match="not found"):
        profile_service.update_profile(db, user_id="does-not-exist", display_name="X")
