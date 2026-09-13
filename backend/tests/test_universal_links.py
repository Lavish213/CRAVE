"""
Coverage for app/api/v1/routes/universal_links.py -- the two platform
verification files (served once at app-install time) and the human-facing
HTML fallback pages for anyone who taps a crave.app/... link without the
app installed.
"""
from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import SessionLocal
from app.db.models.city import City
from app.db.models.place import Place
from app.services.profile.profile_service import create_profile, update_profile

client = TestClient(app)


@pytest.fixture()
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_place(db, *, name: str) -> Place:
    city = City(
        id=str(uuid.uuid4()),
        name="Universal Link Test City",
        slug=f"universal-link-test-{uuid.uuid4().hex[:8]}",
        lat=37.8, lng=-122.27, is_active=True,
    )
    db.add(city)
    db.commit()
    place = Place(name=name, city_id=city.id, lat=37.8, lng=-122.27, is_active=True)
    db.add(place)
    db.commit()
    return place


def test_apple_app_site_association_declares_the_associated_paths():
    resp = client.get("/.well-known/apple-app-site-association")
    assert resp.status_code == 200
    details = resp.json()["applinks"]["details"]
    assert len(details) == 1
    assert details[0]["paths"] == ["/place/*", "/rank/*", "/user/*"]
    assert details[0]["appID"].endswith(".com.crave.app")


def test_android_asset_links_declares_the_app_package():
    resp = client.get("/.well-known/assetlinks.json")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["target"]["package_name"] == "com.crave.app"
    assert body[0]["relation"] == ["delegate_permission/common.handle_all_urls"]


def test_place_landing_page_renders_the_real_place_name(db):
    place = _make_place(db, name="Universal Link Test Bistro")
    resp = client.get(f"/place/{place.id}")
    assert resp.status_code == 200
    assert "Universal Link Test Bistro" in resp.text
    assert "text/html" in resp.headers["content-type"]


def test_place_landing_page_falls_back_honestly_for_an_unknown_id():
    resp = client.get(f"/place/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert "out of date" in resp.text.lower()


def test_rank_landing_page_renders_the_real_place_name(db):
    place = _make_place(db, name="Universal Link Rank Test Diner")
    resp = client.get(f"/rank/{place.id}")
    assert resp.status_code == 200
    assert "Universal Link Rank Test Diner" in resp.text


def _make_profile(db, *, username: str, display_name: str, is_public: bool):
    user_id = str(uuid.uuid4())
    create_profile(db, user_id=user_id, username=username, display_name=display_name)
    update_profile(db, user_id=user_id, is_public=is_public)
    return user_id


def test_user_landing_page_shows_display_name_for_a_public_profile(db):
    user_id = _make_profile(
        db, username=f"pub{uuid.uuid4().hex[:8]}", display_name="Public Test User", is_public=True,
    )
    resp = client.get(f"/user/{user_id}")
    assert resp.status_code == 200
    assert "Public Test User" in resp.text


def test_user_landing_page_never_leaks_a_private_profiles_name(db):
    user_id = _make_profile(
        db, username=f"priv{uuid.uuid4().hex[:8]}", display_name="Private Test User", is_public=False,
    )
    resp = client.get(f"/user/{user_id}")
    assert resp.status_code == 200
    assert "Private Test User" not in resp.text


def test_user_landing_page_falls_back_honestly_for_an_unknown_id():
    resp = client.get(f"/user/{uuid.uuid4()}")
    assert resp.status_code == 200
    assert "out of date" in resp.text.lower()
