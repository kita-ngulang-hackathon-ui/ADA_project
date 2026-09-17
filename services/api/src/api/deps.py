"""Shared FastAPI dependencies: the engine singleton and a tenant-scoped
session factory built on persistence.session.tenant_session.

Every router handler that touches the database takes `tenant_id` from
`auth.require_tenant_api_key` or `auth.require_console_reviewer` and opens
its own `tenant_session` -- there is no repository call anywhere in this
service that accepts a raw tenant filter as the only guard (ARCHITECTURE.md
§11): RLS backs every query issued through the yielded session.
"""
from __future__ import annotations

from contextlib import AbstractContextManager
from functools import lru_cache

from persistence.session import make_engine, tenant_session
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from api.settings import get_settings


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return make_engine(
        settings.database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        echo=settings.db_echo,
    )


def db_for_tenant(tenant_id: str) -> AbstractContextManager[Session]:
    """Open one tenant-scoped transaction. Routers use it as
    `with db_for_tenant(tenant_id) as session: ...` rather than through
    FastAPI's Depends(), because the tenant_id itself only becomes known
    after auth runs earlier in the same handler.
    """
    return tenant_session(get_engine(), tenant_id)
