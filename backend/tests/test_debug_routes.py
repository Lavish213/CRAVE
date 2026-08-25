"""
Coverage for app/api/v1/routes/debug.py — a manual, one-shot way to confirm
SENTRY_DSN is actually wired end-to-end (not just present as an env var) by
deliberately raising and letting app/main.py's global_exception_handler run
for real.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.v1.routes import debug as debug_route
from app.core.rate_limit import rate_limit

# raise_server_exceptions=False: this route deliberately raises, and by
# default TestClient re-raises unhandled exceptions instead of running them
# through app.main's global_exception_handler (its normal path in a real
# deployment). Disabling that here is what actually exercises the handler
# and gets back the real 500 JSON response instead of the raw exception.
client = TestClient(app, raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _override_rate_limit():
    # rate_limit is keyed globally per-IP across every route in the app,
    # not per-endpoint -- this file alone calls debug endpoints ~20 times,
    # sharing the same in-memory bucket as every other test file's
    # TestClient requests in the same run. Added here now that debug.py's
    # router carries rate_limit at all (previously nothing to override),
    # matching the override pattern already used elsewhere in this suite.
    app.dependency_overrides[rate_limit] = lambda: None
    yield
    app.dependency_overrides.pop(rate_limit, None)


def _running_on_postgres() -> bool:
    # This repo's own CI runs the whole suite a second time against a real
    # Postgres instance (that's how a real production bug in
    # search_query.py's SELECT DISTINCT + ORDER BY was caught -- SQLite
    # silently allows what Postgres rejects). The map/categories-query-plan
    # endpoints behave differently by design depending on which database is
    # actually connected, so these tests need to know which one that is
    # rather than assuming SQLite.
    from app.db.session import engine
    return str(engine.url).startswith("postgresql")


def test_sentry_test_endpoint_bypasses_auth_when_api_key_unset(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.get("/api/v1/debug/sentry-test")
    assert response.status_code == 500


def test_sentry_test_endpoint_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "fixture-debug-key")
    response = client.get("/api/v1/debug/sentry-test")
    assert response.status_code == 401


def test_sentry_test_endpoint_raises_with_correct_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "fixture-debug-key")
    response = client.get(
        "/api/v1/debug/sentry-test",
        headers={"x-api-key": "fixture-debug-key"},
    )
    # The deliberate RuntimeError is caught by the global exception handler
    # (app/main.py) and turned into a generic 500 — same as any other
    # unhandled error in prod. This 500 landing in Sentry is the actual
    # thing being verified; that part still requires checking the Sentry
    # project dashboard by hand.
    assert response.status_code == 500


def test_version_reads_the_deploy_stamped_commit_file_first(monkeypatch, tmp_path):
    commit_file = tmp_path / "GIT_COMMIT.txt"
    commit_file.write_text("fileeeeef456abc123def456abc123def456abc\n")
    monkeypatch.setattr(debug_route, "_GIT_COMMIT_FILE", commit_file)
    # Present to prove the file wins even when an env var also resolves —
    # this project's actual deploy method (railway up, a local-directory
    # upload) doesn't set this at all, but a future GitHub-connected
    # deploy might, and the file should still take priority since it's
    # stamped from the exact commit that was actually uploaded.
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "envvarrrf456abc123def456abc123def456abc")

    response = client.get("/api/v1/debug/version")

    assert response.status_code == 200
    body = response.json()
    assert body["commit"] == "fileeeeef456abc123def456abc123def456abc"
    assert body["commit_short"] == "fileeeeef456"


def test_version_falls_back_to_railways_env_var_when_no_commit_file_exists(monkeypatch, tmp_path):
    monkeypatch.setattr(debug_route, "_GIT_COMMIT_FILE", tmp_path / "does-not-exist.txt")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123def456abc123def456abc123def456abc")
    monkeypatch.setenv("RAILWAY_ENVIRONMENT_NAME", "production")

    response = client.get("/api/v1/debug/version")

    assert response.status_code == 200
    body = response.json()
    assert body["commit"] == "abc123def456abc123def456abc123def456abc"
    assert body["commit_short"] == "abc123def456"
    assert body["railway_environment"] == "production"


def test_version_never_requires_an_api_key(monkeypatch):
    monkeypatch.setenv("API_KEY", "fixture-debug-key")
    response = client.get("/api/v1/debug/version")
    assert response.status_code == 200


def test_every_debug_route_enforces_rate_limit():
    """
    The actual security gap this covers: 5 of these 6 endpoints were
    require_api_key-gated but carried no rate_limit at all before this,
    and /version had neither guard -- a caller with the API key (which
    ships inside the public app bundle, not a real secret) could hammer
    the EXPLAIN ANALYZE endpoints freely. Asserts the dependency is
    actually wired, not just present somewhere in the router's kwargs.
    """
    from app.main import app as real_app

    real_app.dependency_overrides.pop(rate_limit, None)
    try:
        for route in real_app.router.routes:
            if not str(getattr(route, "path", "")).startswith("/api/v1/debug/"):
                continue
            dependant = getattr(route, "dependant", None)
            assert dependant is not None
            assert any(
                dep.call is rate_limit for dep in dependant.dependencies
            ), f"{route.path} is missing rate_limit"
    finally:
        real_app.dependency_overrides[rate_limit] = lambda: None


def test_scheduler_diagnostics_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "fixture-debug-key")
    response = client.get("/api/v1/debug/scheduler")
    assert response.status_code == 401


def test_scheduler_diagnostics_reports_flag_and_recent_job_runs(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)

    from datetime import datetime, timedelta, timezone
    from app.db.session import SessionLocal
    from app.db.models.job_run import JobRun

    db = SessionLocal()
    try:
        started = datetime.now(timezone.utc) - timedelta(seconds=67)
        finished = started + timedelta(seconds=67)
        db.add(
            JobRun(
                job_name="test_diagnostic_job",
                started_at=started,
                finished_at=finished,
                success=True,
                summary="processed=1",
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/debug/scheduler")

    assert response.status_code == 200
    body = response.json()
    assert "run_embedded_scheduler" in body
    names = [r["job_name"] for r in body["recent_runs"]]
    assert "test_diagnostic_job" in names
    match = next(r for r in body["recent_runs"] if r["job_name"] == "test_diagnostic_job")
    assert match["success"] is True
    assert match["still_running_or_crashed"] is False
    assert match["duration_seconds"] == pytest.approx(67.0, abs=1.0)


def test_scheduler_diagnostics_flags_still_running_job(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)

    from datetime import datetime, timezone
    from app.db.session import SessionLocal
    from app.db.models.job_run import JobRun

    db = SessionLocal()
    try:
        db.add(
            JobRun(
                job_name="test_stuck_job",
                started_at=datetime.now(timezone.utc),
                finished_at=None,
                success=None,
                summary=None,
            )
        )
        db.commit()
    finally:
        db.close()

    response = client.get("/api/v1/debug/scheduler")

    assert response.status_code == 200
    body = response.json()
    match = next(r for r in body["recent_runs"] if r["job_name"] == "test_stuck_job")
    assert match["still_running_or_crashed"] is True
    assert match["finished_at"] is None


def test_map_query_plan_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "fixture-debug-key")
    response = client.get("/api/v1/debug/map-query-plan?lat=37.7749&lng=-122.4194")
    assert response.status_code == 401


@pytest.mark.skipif(_running_on_postgres(), reason="this checks the non-Postgres no-op path")
def test_map_query_plan_no_ops_safely_on_non_postgres_db(monkeypatch):
    # EXPLAIN (FORMAT JSON) is Postgres-only syntax, so on SQLite this must
    # degrade to a clean error response, never a 500.
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.get("/api/v1/debug/map-query-plan?lat=37.7749&lng=-122.4194")
    assert response.status_code == 200
    body = response.json()
    assert "error" in body
    assert "Postgres" in body["error"]


@pytest.mark.skipif(not _running_on_postgres(), reason="this checks the real Postgres path")
def test_map_query_plan_returns_a_real_explain_plan_on_postgres(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.get("/api/v1/debug/map-query-plan?lat=37.7749&lng=-122.4194")
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert body["explain_plan_error"] is None
    assert body["explain_plan"] is not None


def test_categories_query_plan_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "fixture-debug-key")
    response = client.get("/api/v1/debug/categories-query-plan?lat=37.7749&lng=-122.4194")
    assert response.status_code == 401


@pytest.mark.skipif(_running_on_postgres(), reason="this checks the non-Postgres no-op path")
def test_categories_query_plan_no_ops_safely_on_non_postgres_db(monkeypatch):
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.get("/api/v1/debug/categories-query-plan?lat=37.7749&lng=-122.4194")
    assert response.status_code == 200
    body = response.json()
    assert "error" in body
    assert "Postgres" in body["error"]


@pytest.mark.skipif(not _running_on_postgres(), reason="this checks the real Postgres path")
def test_categories_query_plan_finds_place_ids_on_postgres(monkeypatch):
    # conftest.py seeds a place at exactly this lat/lng -- a generous
    # radius guarantees a non-empty bbox so this actually exercises the
    # EXPLAIN query rather than short-circuiting on "no place_ids in bbox".
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.get(
        "/api/v1/debug/categories-query-plan?lat=37.8044&lng=-122.2712&radius_km=5"
    )
    assert response.status_code == 200
    body = response.json()
    assert "error" not in body
    assert body["place_ids_count"] >= 1
    assert body["explain_plan_error"] is None


def test_map_query_timing_requires_api_key_when_configured(monkeypatch):
    monkeypatch.setenv("API_KEY", "fixture-debug-key")
    response = client.get("/api/v1/debug/map-query-timing?lat=37.8044&lng=-122.2712")
    assert response.status_code == 401


def test_map_query_timing_reports_per_phase_breakdown(monkeypatch):
    # Uses conftest.py's seeded place (lat=37.8044, lng=-122.2712) -- unlike
    # map-query-plan, this hits real ORM code paths that work on SQLite too,
    # so it's a genuine (not no-op) exercise of the production functions.
    monkeypatch.delenv("API_KEY", raising=False)
    response = client.get(
        "/api/v1/debug/map-query-timing?lat=37.8044&lng=-122.2712&radius_km=5"
    )
    assert response.status_code == 200
    body = response.json()
    assert body["place_ids_count"] >= 1
    assert body["categories_bulk_error"] is None
    assert body["images_bulk_error"] is None
    for key in (
        "base_query_seconds", "categories_bulk_seconds",
        "images_bulk_seconds", "total_seconds",
    ):
        assert isinstance(body[key], (int, float))
