"""Pure-logic auth tests -- no database needed."""
import time

import pytest
from api import errors
from api.auth import _sign, _verify, hash_api_key, issue_session_cookie, require_console_reviewer
from api.settings import Settings


def test_hash_api_key_is_deterministic():
    assert hash_api_key("demo-wallet-key", "pepper1") == hash_api_key("demo-wallet-key", "pepper1")


def test_hash_api_key_differs_by_pepper():
    assert hash_api_key("demo-wallet-key", "pepper1") != hash_api_key("demo-wallet-key", "pepper2")


def test_sign_and_verify_roundtrip():
    payload = {"tenant_id": "t1", "tenant_slug": "demo-wallet", "reviewer_id": "ops_reviewer_1"}
    token = _sign(payload, "secret")
    assert _verify(token, "secret") == payload


def test_verify_rejects_tampered_token():
    token = _sign({"reviewer_id": "ops_reviewer_1"}, "secret")
    body, sig = token.rsplit(".", 1)
    tampered = f"{body}x.{sig}"
    assert _verify(tampered, "secret") is None


def test_verify_rejects_wrong_secret():
    token = _sign({"reviewer_id": "ops_reviewer_1"}, "secret-a")
    assert _verify(token, "secret-b") is None


def test_verify_rejects_malformed_token():
    assert _verify("not-a-valid-token", "secret") is None
    assert _verify("", "secret") is None


def _settings(**overrides) -> Settings:
    base = {
        "database_url": "postgresql+psycopg://app_console:x@localhost:5432/retention_test",
        "api_key_hash_pepper": "test-pepper",
        "console_session_secret": "test-console-secret",
        "console_demo_reviewers": "ops_reviewer_1",
    }
    return Settings(**{**base, **overrides})


def test_console_cookie_carries_an_expiry():
    settings = _settings()
    token = issue_session_cookie(
        tenant_id="t1", tenant_slug="demo-wallet", reviewer_id="ops_reviewer_1", settings=settings
    )
    payload = _verify(token, settings.console_session_secret)
    assert payload["exp"] > int(time.time())

    session = require_console_reviewer(console_session=token, settings=settings)
    assert session.reviewer_id == "ops_reviewer_1"


def test_expired_console_cookie_is_rejected():
    settings = _settings(console_session_ttl_seconds=-1)
    token = issue_session_cookie(
        tenant_id="t1", tenant_slug="demo-wallet", reviewer_id="ops_reviewer_1", settings=settings
    )
    with pytest.raises(errors.ApiError) as raised:
        require_console_reviewer(console_session=token, settings=settings)
    assert raised.value.http_status == 401


def test_cookie_without_expiry_is_rejected():
    settings = _settings()
    token = _sign(
        {"tenant_id": "t1", "tenant_slug": "demo-wallet", "reviewer_id": "ops_reviewer_1"},
        settings.console_session_secret,
    )
    with pytest.raises(errors.ApiError) as raised:
        require_console_reviewer(console_session=token, settings=settings)
    assert raised.value.http_status == 401
