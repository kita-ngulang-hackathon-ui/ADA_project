"""Authentication dependencies.

Two surfaces, two mechanisms (API_CONTRACTS.md):
- Ingestion API: `Authorization: Bearer <api_key>` -> tenant, via api_keys.key_hash.
- Console API: a signed session cookie carrying tenant + reviewer identity.

The console session cookie is deliberately minimal for the demo (no
password): `POST /console/v1/session` accepts a reviewer_id that must
already be in CONSOLE_DEMO_REVIEWERS and a tenant_slug, and issues a cookie
HMAC-signed with CONSOLE_SESSION_SECRET. There is no code path that can
mint a reviewer identity that was not already on that allow-list, and
`require_console_reviewer` never defaults one when the cookie is absent
(requirement 8 -- the same rule core_contracts.assert_transition enforces).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json

from fastapi import Cookie, Depends, Header
from persistence.repositories import tenants as tenants_repo
from persistence.session import make_engine
from sqlalchemy.orm import Session

from api import errors
from api.settings import Settings, get_settings

SESSION_COOKIE_NAME = "console_session"


def unscoped_session(settings: Settings) -> Session:
    """A session with no tenant_id set -- only used for the two lookups that
    must happen BEFORE a tenant is known: API key resolution and console
    session issuance. RLS still applies; queries here only ever touch
    `tenants` / `api_keys`, which are RLS-exempt for exactly this reason."""
    engine = make_engine(settings.database_url, pool_size=1, max_overflow=0)
    return Session(bind=engine)


def hash_api_key(raw_key: str, pepper: str) -> str:
    return hmac.new(pepper.encode("utf-8"), raw_key.encode("utf-8"), hashlib.sha256).hexdigest()


def require_tenant_api_key(
    authorization: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """Bearer token -> tenant_id (str UUID). Constant-time compare on the
    hash lookup path is provided by the database equality scan matching a
    fixed-length hash, not by comparing the raw key in Python; the raw key
    itself never touches a second comparison after hashing."""
    if not authorization or not authorization.startswith("Bearer "):
        raise errors.unauthenticated("Expected Authorization: Bearer <api_key>")
    raw_key = authorization.removeprefix("Bearer ").strip()
    if not raw_key:
        raise errors.unauthenticated("Empty API key")

    key_hash = hash_api_key(raw_key, settings.api_key_hash_pepper)
    session = unscoped_session(settings)
    try:
        tenant = tenants_repo.get_tenant_for_api_key(session, key_hash=key_hash)
    finally:
        session.close()

    if tenant is None:
        raise errors.unauthenticated("Unknown or inactive API key")
    return str(tenant.id)


def _sign(payload: dict, secret: str) -> str:
    body = base64.urlsafe_b64encode(json.dumps(payload, sort_keys=True).encode("utf-8")).decode("ascii")
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}"


def _verify(token: str, secret: str) -> dict | None:
    try:
        body, sig = token.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        return json.loads(base64.urlsafe_b64decode(body.encode("ascii")))
    except (ValueError, UnicodeDecodeError):
        return None


def issue_session_cookie(*, tenant_id: str, tenant_slug: str, reviewer_id: str, settings: Settings) -> str:
    return _sign(
        {"tenant_id": tenant_id, "tenant_slug": tenant_slug, "reviewer_id": reviewer_id},
        settings.console_session_secret,
    )


class ConsoleSession:
    def __init__(self, tenant_id: str, tenant_slug: str, reviewer_id: str):
        self.tenant_id = tenant_id
        self.tenant_slug = tenant_slug
        self.reviewer_id = reviewer_id


def require_console_reviewer(
    console_session: str | None = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    settings: Settings = Depends(get_settings),
) -> ConsoleSession:
    """Session -> reviewer_id, asserted to be in CONSOLE_DEMO_REVIEWERS.
    Never defaults the reviewer id (requirement 8): a missing or invalid
    cookie is 401, full stop, regardless of CONSOLE_REQUIRE_REVIEWER_ID --
    that flag exists only to document the rule is non-optional, not to make
    it toggleable."""
    if not console_session:
        raise errors.unauthenticated("No console session")
    payload = _verify(console_session, settings.console_session_secret)
    if payload is None:
        raise errors.unauthenticated("Invalid or tampered console session")
    reviewer_id = payload.get("reviewer_id")
    if not reviewer_id or reviewer_id not in settings.demo_reviewer_set:
        raise errors.forbidden("reviewer_id is not on the approved reviewer list")
    return ConsoleSession(
        tenant_id=payload["tenant_id"], tenant_slug=payload["tenant_slug"], reviewer_id=reviewer_id
    )
