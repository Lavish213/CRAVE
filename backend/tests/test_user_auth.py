"""
Unit tests for app.core.user_auth.get_current_user_id's actual token
verification logic.

Every route-level test in this suite bypasses get_current_user_id entirely
via app.dependency_overrides -- which means, until this file, the real
cryptographic verification path (JWKS fetch, signature check, audience/exp
claims) had zero test coverage. That gap is exactly how the ES256 migration
bug shipped silently: nothing exercised the actual jwt.decode() call against
a real signature.

These tests generate a real EC (P-256) key pair, sign tokens with the
private key (standing in for Supabase), and monkeypatch
user_auth._get_jwks_client() to return the public half -- standing in for
what Supabase's JWKS endpoint would serve -- so no real network call is
made.
"""
from __future__ import annotations

import time

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi import HTTPException
from jwt import PyJWK

from app.config.settings import settings
from app.core import user_auth


@pytest.fixture
def ec_keypair():
    private_key = ec.generate_private_key(ec.SECP256R1())
    return private_key, private_key.public_key()


def _sign(private_key, *, sub="user-123", aud="authenticated", exp_delta=3600, kid="test-kid"):
    now = int(time.time())
    payload = {"sub": sub, "aud": aud, "iat": now, "exp": now + exp_delta}
    return jwt.encode(payload, private_key, algorithm="ES256", headers={"kid": kid})


class _FakeJWKSClient:
    """Stands in for PyJWKClient, returning a fixed public key regardless
    of the token's kid -- these tests aren't exercising key-rotation
    lookup, just what get_current_user_id does with whatever key it gets
    back."""

    def __init__(self, public_key):
        self._jwk = PyJWK.from_json(
            __import__("json").dumps(
                jwt.algorithms.ECAlgorithm.to_jwk(public_key, as_dict=True)
            )
        )

    def get_signing_key_from_jwt(self, token):
        return self._jwk


@pytest.fixture(autouse=True)
def _reset_jwks_client_cache():
    # get_current_user_id caches one PyJWKClient at module scope; make sure
    # a real one built by an earlier/later test doesn't leak across tests.
    user_auth._jwks_client = None
    yield
    user_auth._jwks_client = None


@pytest.fixture
def configured_supabase_url(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://example.supabase.co")


def test_valid_token_returns_the_subject_claim_as_user_id(ec_keypair, configured_supabase_url, monkeypatch):
    private_key, public_key = ec_keypair
    monkeypatch.setattr(user_auth, "_get_jwks_client", lambda: _FakeJWKSClient(public_key))

    token = _sign(private_key, sub="the-real-user-id")

    user_id = user_auth.get_current_user_id(authorization=f"Bearer {token}")

    assert user_id == "the-real-user-id"


def test_token_signed_with_a_different_key_is_rejected(ec_keypair, configured_supabase_url, monkeypatch):
    _, public_key = ec_keypair
    forged_private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(user_auth, "_get_jwks_client", lambda: _FakeJWKSClient(public_key))

    forged_token = _sign(forged_private_key, sub="attacker")

    with pytest.raises(HTTPException) as exc_info:
        user_auth.get_current_user_id(authorization=f"Bearer {forged_token}")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


def test_expired_token_is_rejected(ec_keypair, configured_supabase_url, monkeypatch):
    private_key, public_key = ec_keypair
    monkeypatch.setattr(user_auth, "_get_jwks_client", lambda: _FakeJWKSClient(public_key))

    expired_token = _sign(private_key, exp_delta=-60)

    with pytest.raises(HTTPException) as exc_info:
        user_auth.get_current_user_id(authorization=f"Bearer {expired_token}")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Token expired"


def test_wrong_audience_is_rejected(ec_keypair, configured_supabase_url, monkeypatch):
    private_key, public_key = ec_keypair
    monkeypatch.setattr(user_auth, "_get_jwks_client", lambda: _FakeJWKSClient(public_key))

    token = _sign(private_key, aud="some-other-project")

    with pytest.raises(HTTPException) as exc_info:
        user_auth.get_current_user_id(authorization=f"Bearer {token}")

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid token"


def test_missing_bearer_token_raises_401_when_supabase_url_configured(configured_supabase_url):
    with pytest.raises(HTTPException) as exc_info:
        user_auth.get_current_user_id(authorization=None)

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Missing bearer token"


def test_dev_bypass_returns_fixed_id_when_supabase_url_unset_and_not_prod(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "app_env", "dev")

    user_id = user_auth.get_current_user_id(authorization=None)

    assert user_id == user_auth._DEV_FALLBACK_USER_ID


def test_missing_token_in_prod_raises_401_even_with_supabase_url_unset(monkeypatch):
    # Belt-and-suspenders: app/main.py's startup guard should already have
    # refused to boot in this state, but get_current_user_id must not
    # silently dev-bypass in prod even if that guard were somehow bypassed.
    monkeypatch.setattr(settings, "supabase_url", "")
    monkeypatch.setattr(settings, "app_env", "prod")

    with pytest.raises(HTTPException) as exc_info:
        user_auth.get_current_user_id(authorization=None)

    assert exc_info.value.status_code == 401


def test_token_present_but_supabase_url_unset_returns_500(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "")

    with pytest.raises(HTTPException) as exc_info:
        user_auth.get_current_user_id(authorization="Bearer some-token")

    assert exc_info.value.status_code == 500


def test_get_current_user_id_optional_returns_none_on_invalid_token(ec_keypair, configured_supabase_url, monkeypatch):
    _, public_key = ec_keypair
    forged_private_key = ec.generate_private_key(ec.SECP256R1())
    monkeypatch.setattr(user_auth, "_get_jwks_client", lambda: _FakeJWKSClient(public_key))

    forged_token = _sign(forged_private_key)

    assert user_auth.get_current_user_id_optional(authorization=f"Bearer {forged_token}") is None


def test_get_current_user_id_optional_returns_subject_on_valid_token(ec_keypair, configured_supabase_url, monkeypatch):
    private_key, public_key = ec_keypair
    monkeypatch.setattr(user_auth, "_get_jwks_client", lambda: _FakeJWKSClient(public_key))

    token = _sign(private_key, sub="optional-path-user")

    assert user_auth.get_current_user_id_optional(authorization=f"Bearer {token}") == "optional-path-user"
