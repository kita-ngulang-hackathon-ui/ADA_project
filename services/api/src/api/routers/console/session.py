"""POST /console/v1/session -- issues the signed console session cookie.

Not one of the endpoints API_CONTRACTS.md names, but necessary glue: the
console auth mechanism it specifies ("session cookie with tenant + reviewer
identity") has to be issued somewhere. There is no password for the demo --
the reviewer picks their identity from CONSOLE_DEMO_REVIEWERS, matching
DEMO_SCRIPT.md beat 4 ("select reviewer ops_reviewer_1"). The only thing
this endpoint can never do is mint a reviewer_id that was not already on
that allow-list (requirement 8: no default, no system reviewer).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from persistence.repositories import tenants as tenants_repo
from pydantic import BaseModel

from api import errors
from api.auth import SESSION_COOKIE_NAME, issue_session_cookie, unscoped_session
from api.settings import Settings, get_settings

router = APIRouter(prefix="/console/v1", tags=["console-session"])


class SessionIn(BaseModel):
    tenant_slug: str
    reviewer_id: str


class SessionOut(BaseModel):
    tenant_id: str
    tenant_slug: str
    reviewer_id: str


@router.post("/session")
def create_session(
    body: SessionIn, response: Response, settings: Settings = Depends(get_settings)
) -> SessionOut:
    if body.reviewer_id not in settings.demo_reviewer_set:
        raise errors.forbidden(
            f"{body.reviewer_id!r} is not in CONSOLE_DEMO_REVIEWERS; there is no default reviewer"
        )

    session = unscoped_session(settings)
    try:
        tenant = tenants_repo.get_by_slug(session, slug=body.tenant_slug)
    finally:
        session.close()
    if tenant is None:
        raise errors.not_found(f"tenant {body.tenant_slug!r} not found")

    cookie = issue_session_cookie(
        tenant_id=str(tenant.id), tenant_slug=tenant.slug, reviewer_id=body.reviewer_id, settings=settings
    )
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=cookie,
        httponly=True,
        samesite="lax",
        max_age=settings.console_session_ttl_seconds,
        secure=settings.app_env != "local",
    )
    return SessionOut(tenant_id=str(tenant.id), tenant_slug=tenant.slug, reviewer_id=body.reviewer_id)
