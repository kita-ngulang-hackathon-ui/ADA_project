"""Engine + tenant-scoped session with Row-Level Security.

TODO:
- make_engine(database_url, pool_size, max_overflow, echo).
- tenant_session(engine, tenant_id): begin tx, SET LOCAL app.tenant_id, yield session.
"""
from contextlib import contextmanager


def make_engine(database_url: str, *, pool_size: int = 5, max_overflow: int = 5, echo: bool = False):
    raise NotImplementedError


@contextmanager
def tenant_session(engine, tenant_id: str):
    raise NotImplementedError
    yield  # pragma: no cover
