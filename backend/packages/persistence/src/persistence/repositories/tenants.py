"""Tenant directory reads. Tenant lookup by API key / slug happens outside
RLS (there is no tenant_id to scope by yet), so these queries run on an
un-scoped session the caller must obtain separately from tenant_session."""
from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from persistence.models import ApiKey, Tenant


def list_tenants(session: Session) -> list[Tenant]:
    return list(session.execute(select(Tenant).order_by(Tenant.slug)).scalars().all())


def get_by_slug(session: Session, *, slug: str) -> Tenant | None:
    return session.execute(select(Tenant).where(Tenant.slug == slug)).scalar_one_or_none()


def get_by_id(session: Session, *, tenant_id: uuid.UUID | str) -> Tenant | None:
    return session.execute(select(Tenant).where(Tenant.id == tenant_id)).scalar_one_or_none()


def get_tenant_for_api_key(session: Session, *, key_hash: str) -> Tenant | None:
    """Bearer-key -> tenant resolution for the ingestion API. Constant-time
    comparison happens in api.auth before key_hash is computed/looked up;
    this is a plain equality lookup on the hash, not the raw key."""
    stmt = (
        select(Tenant)
        .join(ApiKey, ApiKey.tenant_id == Tenant.id)
        .where(ApiKey.key_hash == key_hash, ApiKey.active.is_(True))
    )
    return session.execute(stmt).scalar_one_or_none()
