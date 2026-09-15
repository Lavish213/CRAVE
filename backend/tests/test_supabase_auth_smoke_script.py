from __future__ import annotations

from scripts import smoke_supabase_auth as smoke


def test_smoke_reports_missing_supabase_url(monkeypatch):
    monkeypatch.setattr(smoke.settings, "supabase_url", "")

    code, result = smoke.run_smoke(
        token_env="MISSING_TOKEN",
        require_token=False,
        skip_jwks_fetch=True,
        timeout=0.01,
    )

    assert code == 2
    assert result["errors"] == ["SUPABASE_URL is not set"]
    assert result["token_verified"] is False


def test_smoke_can_validate_config_without_printing_token(monkeypatch):
    monkeypatch.setattr(smoke.settings, "supabase_url", "https://example.supabase.co")
    monkeypatch.setenv("SMOKE_TOKEN", "secret-token-value")
    monkeypatch.setattr(smoke, "get_current_user_id", lambda authorization: "user-abcdef123456")

    code, result = smoke.run_smoke(
        token_env="SMOKE_TOKEN",
        require_token=True,
        skip_jwks_fetch=True,
        timeout=0.01,
    )

    assert code == 0
    assert result["token_present"] is True
    assert result["token_verified"] is True
    assert result["user_id_suffix"] == "ef123456"
    assert "secret-token-value" not in str(result)
