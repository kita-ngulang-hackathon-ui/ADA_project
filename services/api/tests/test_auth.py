"""Pure-logic auth tests -- no database needed."""
from api.auth import _sign, _verify, hash_api_key


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
