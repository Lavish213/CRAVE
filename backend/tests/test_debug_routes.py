"""
Coverage for app/api/v1/routes/debug.py — a manual, one-shot way to confirm
SENTRY_DSN is actually wired end-to-end (not just present as an env var) by
deliberately raising and letting app/main.py's global_exception_handler run
for real.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

# raise_server_exceptions=False: this route deliberately raises, and by
# default TestClient re-raises unhandled exceptions instead of running them
# through app.main's global_exception_handler (its normal path in a real
# deployment). Disabling that here is what actually exercises the handler
# and gets back the real 500 JSON response instead of the raw exception.
client = TestClient(app, raise_server_exceptions=False)


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


def test_version_reports_railways_own_commit_env_var_when_set(monkeypatch):
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
