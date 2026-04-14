# tests/hitlist/test_hitlist_routes.py
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_save_returns_201():
    resp = client.post("/api/v1/hitlist/save", json={
        "user_id": "user-test-1",
        "place_name": "Joe's Tacos",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == "saved"
    assert "id" in data

def test_save_with_tiktok_url():
    resp = client.post("/api/v1/hitlist/save", json={
        "user_id": "user-test-2",
        "place_name": "Birria House",
        "source_url": "https://www.tiktok.com/@foodie/video/7123456789",
    })
    assert resp.status_code == 201

def test_save_dedup_returns_same_id():
    payload = {"user_id": "user-dedup-1", "place_name": "Repeat Spot"}
    r1 = client.post("/api/v1/hitlist/save", json=payload)
    r2 = client.post("/api/v1/hitlist/save", json=payload)
    assert r1.status_code == 201
    assert r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]

def test_get_hitlist():
    user_id = "user-get-1"
    client.post("/api/v1/hitlist/save", json={"user_id": user_id, "place_name": "Test Place"})
    resp = client.get(f"/api/v1/hitlist/{user_id}")
    assert resp.status_code == 200
    data = resp.json()
    assert "items" in data
    assert data["total"] >= 1
    item = data["items"][0]
    assert item["place_name"] == "Test Place"
    assert item["resolution_status"] == "raw"

def test_delete_save():
    user_id = "user-del-1"
    client.post("/api/v1/hitlist/save", json={"user_id": user_id, "place_name": "Delete Me"})
    resp = client.delete(f"/api/v1/hitlist/delete?user_id={user_id}&place_name=Delete+Me")
    assert resp.status_code == 200
    assert resp.json()["status"] == "deleted"

def test_delete_nonexistent_returns_404():
    resp = client.delete("/api/v1/hitlist/delete?user_id=nobody&place_name=NoPlace")
    assert resp.status_code == 404

def test_suggest_returns_201():
    resp = client.post("/api/v1/hitlist/suggest", json={
        "user_id": "user-sug-1",
        "place_name": "New Discovery",
        "city_hint": "Oakland",
    })
    assert resp.status_code == 201
    data = resp.json()
    assert "id" in data
    assert data["place_name"] == "New Discovery"

def test_analytics_endpoint():
    resp = client.get("/api/v1/hitlist/analytics/summary")
    assert resp.status_code == 200
    data = resp.json()
    for key in ("saves_today", "unresolved_count", "promoted_count", "top_saved_places"):
        assert key in data
