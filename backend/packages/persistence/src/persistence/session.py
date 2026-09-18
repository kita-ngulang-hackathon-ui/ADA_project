"""Engine + tenant-scoped session with Row-Level Security.

`tenant_session` is the ONLY sanctioned way any repository or router obtains
a Session. It runs `SET LOCAL app.tenant_id = :tid` inside the transaction so
Postgres RLS policies (`USING (tenant_id = current_setting('app.tenant_id')::uuid)`)
apply automatically to every query issued through the yielded session --
even one that forgets a `WHERE tenant_id = ...` clause (ARCHITECTURE.md §11).
"""
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker


def make_engine(
    database_url: str,
    *,
    pool_size: int = 5,
    max_overflow: int = 5,
    echo: bool = False,
) -> Engine:
    """Build the SQLAlchemy engine for one of the app_worker / app_console /
    app_readonly database roles. `database_url` already encodes which role
    to connect as (see .env.example DATABASE_URL / WORKER_DATABASE_URL)."""
    return create_engine(
        database_url,
        pool_size=pool_size,
        max_overflow=max_overflow,
        echo=echo,
        pool_pre_ping=True,
    )


@contextmanager
def tenant_session(engine: Engine, tenant_id: str) -> Iterator[Session]:
    """Open one transaction with `app.tenant_id` set for its duration.

    `SET LOCAL` scopes the setting to the current transaction only, so it
    can never leak onto a pooled connection reused by a different tenant's
    request. Repository functions take the yielded Session and never accept
    a raw tenant filter from the caller as the only guard -- RLS is the
    backstop, not the only line of defense.
    """
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    session = session_factory()
    try:
        # Parameterized to avoid SQL injection via a malformed tenant_id;
        # Postgres does not support bind params inside SET LOCAL directly,
        # so validate shape first and use format() defensively.
        _assert_safe_identifier(tenant_id)
        session.execute(text(f"SET LOCAL app.tenant_id = '{tenant_id}'"))
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _assert_safe_identifier(value: str) -> None:
    """tenant_id must be a UUID literal -- reject anything else outright
    rather than interpolating it into SQL."""
    import uuid

    uuid.UUID(str(value))
