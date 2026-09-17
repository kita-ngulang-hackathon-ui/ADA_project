"""Shared FastAPI dependencies: the engine singletons and tenant-scoped
session factories built on persistence.session.tenant_session.

Two engines, two roles (migration 0006): console routes connect as the
console role (the only one that may approve), ingestion routes as the worker
role (the only one that may INSERT raw_events / outcome_events and move a
recommendation to DELIVERED). A route that writes on the wrong one gets a
permission error from Postgres, which is the point.

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


@lru_cache
def get_ingest_engine() -> Engine:
    settings = get_settings()
    return make_engine(
        settings.ingest_database_url,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        echo=settings.db_echo,
    )


def db_for_ingest(tenant_id: str) -> AbstractContextManager[Session]:
    """Tenant-scoped transaction on the ingestion (worker-role) engine. RLS
    applies exactly as it does for `db_for_tenant`."""
    return tenant_session(get_ingest_engine(), tenant_id)


def db_for_tenant(tenant_id: str) -> AbstractContextManager[Session]:
    """Open one tenant-scoped transaction. Routers use it as
    `with db_for_tenant(tenant_id) as session: ...` rather than through
    FastAPI's Depends(), because the tenant_id itself only becomes known
    after auth runs earlier in the same handler.
    """
    return tenant_session(get_engine(), tenant_id)
