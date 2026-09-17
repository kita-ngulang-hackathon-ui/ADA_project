"""GET /console/v1/tenants -- list demo tenants. Not itself tenant-scoped
(that is the whole point -- it is how the tenant switcher in apps/web is
populated before a session for a specific tenant exists)."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from persistence.repositories import tenants as tenants_repo
from pydantic import BaseModel

from api.auth import unscoped_session
from api.settings import Settings, get_settings

router = APIRouter(prefix="/console/v1", tags=["console-tenants"])


class TenantOut(BaseModel):
    tenant_id: str
    slug: str
    display_name: str
    profile_type: str


class TenantList(BaseModel):
    items: list[TenantOut]


@router.get("/tenants")
def list_tenants(settings: Settings = Depends(get_settings)) -> TenantList:
    session = unscoped_session(settings)
    try:
        rows = tenants_repo.list_tenants(session)
    finally:
        session.close()
    return TenantList(
        items=[
            TenantOut(tenant_id=str(t.id), slug=t.slug, display_name=t.display_name, profile_type=t.profile_type)
            for t in rows
        ]
    )
