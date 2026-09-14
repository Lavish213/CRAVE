from __future__ import annotations

import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.core.rate_limit import rate_limit
from app.core.user_auth import get_current_user_id
from app.db.models.city import City
from app.db.models.job_run import JobRun
from app.db.models.menu_source import MenuSource
from app.db.models.menu_submission import MenuSubmission, STATUS_PENDING
from app.db.models.place import Place
from app.db.models.place_image import PlaceImage
from app.db.session import SessionLocal
from app.main import app

client = TestClient(app)

ADMIN_ID = "data-pipeline-admin-fixture"


def _as_user(user_id: str):
    app.dependency_overrides[get_current_user_id] = lambda: user_id


@pytest.fixture(autouse=True)
def _overrides(monkeypatch):
    app.dependency_overrides[rate_limit] = lambda: None
    monkeypatch.setenv("ADMIN_USER_IDS", ADMIN_ID)
    yield
    app.dependency_overrides.pop(get_current_user_id, None)
    app.dependency_overrides.pop(rate_limit, None)


@pytest.fixture
def db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def place(db):
    suffix = uuid.uuid4().hex[:8]
    city = City(slug=f"pipeline-admin-{suffix}", name=f"Pipeline Admin {suffix}")
    db.add(city)
    db.flush()
    p = Place(name=f"Pipeline Place {suffix}", city_id=city.id, is_active=True)
    db.add(p)
    db.commit()
    yield p
    db.query(JobRun).filter(JobRun.job_name.in_(("menu_enrichment", "image_ingestion"))).delete(synchronize_session=False)
    db.query(PlaceImage).filter(PlaceImage.place_id == p.id).delete()
    db.query(MenuSubmission).filter(MenuSubmission.place_id == p.id).delete()
    db.query(MenuSource).filter(MenuSource.place_id == p.id).delete()
    db.query(Place).filter(Place.id == p.id).delete()
    db.query(City).filter(City.id == city.id).delete()
    db.commit()


def test_data_pipeline_dashboard_is_admin_only(place):
    _as_user("ordinary-user")
    resp = client.get("/api/v1/moderation/data-pipeline/dashboard")
    assert resp.status_code == 404


def test_data_pipeline_dashboard_summarizes_sources_submissions_images_and_jobs(db, place):
    now = datetime.now(timezone.utc)
    db.add(
        MenuSource(
            place_id=place.id,
            source_url="https://order.toasttab.com/online/pipeline-place",
            source_hash=f"toast-{uuid.uuid4().hex}",
            provider="toast",
            source_type="provider",
            confidence=0.95,
            is_active=False,
            last_seen_at=now,
            last_failure_at=now,
            last_failure_reason="access_blocked:provider_api_required",
            invalidation_reason="access_blocked:provider_api_required",
            failure_count=1,
        )
    )
    db.add(
        MenuSource(
            place_id=place.id,
            source_url="https://pipeline.example/menu",
            source_hash=f"html-{uuid.uuid4().hex}",
            provider="html",
            source_type="official_html",
            confidence=0.88,
            is_active=True,
            last_seen_at=now,
        )
    )
    db.add(
        MenuSubmission(
            place_id=place.id,
            submitted_by="menu-helper",
            items=[{"name": "Miso Ramen", "price_cents": 1500}],
            evidence_url="https://pipeline.example/menu.pdf",
            status=STATUS_PENDING,
        )
    )
    db.add(
        PlaceImage(
            place_id=place.id,
            url="places/google/photos/abc",
            source_provider="google",
            source_context="google_places",
            source_metadata={"html_attributions": ["Owner"]},
        )
    )
    db.add(
        PlaceImage(
            place_id=place.id,
            url="https://legacy.example/photo.jpg",
        )
    )
    db.add(
        JobRun(
            job_name="menu_enrichment",
            started_at=now,
            finished_at=now,
            success=True,
            summary="processed=10 published=3",
        )
    )
    db.commit()

    _as_user(ADMIN_ID)
    resp = client.get("/api/v1/moderation/data-pipeline/dashboard")
    assert resp.status_code == 200
    body = resp.json()

    assert body["menu_sources"]["total"] >= 2
    assert body["menu_sources"]["active"] >= 1
    assert body["menu_sources"]["inactive"] >= 1
    assert body["menu_sources"]["provider_access_required"] >= 1
    assert body["menu_sources"]["by_provider"]["toast"] >= 1
    assert any(
        row["last_failure_reason"] == "access_blocked:provider_api_required"
        for row in body["menu_sources"]["recent_failures"]
    )

    assert body["menu_submissions"]["pending"] >= 1
    assert body["menu_submissions"]["pending_with_evidence"] >= 1
    assert any(
        row["evidence_url"] == "https://pipeline.example/menu.pdf"
        for row in body["menu_submissions"]["recent_pending"]
    )

    assert body["image_sources"]["with_provenance"] >= 1
    assert body["image_sources"]["missing_provenance"] >= 1
    assert body["image_sources"]["by_provider"]["google"] >= 1

    assert body["jobs"]["menu_enrichment"]["success"] is True
    assert body["jobs"]["menu_enrichment"]["summary"] == "processed=10 published=3"
