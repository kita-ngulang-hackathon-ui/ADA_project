"""Shared fixtures for the two Postgres-backed invariants.

Reads connection info from the environment (already exported) or, failing
that, parses the repo-root `.env` directly -- these tests must be runnable
via a plain `pytest tests/invariants`, not only through `make test-invariants`
after a manual `source .env`. If neither source has what's needed, every
test that depends on these fixtures is skipped with a clear reason, per the
project's own rule: a skip must say why, never fail silently and never be
mistaken for a pass.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest
import sqlalchemy as sa

_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"


def _load_dotenv_if_needed() -> dict[str, str]:
    """Merge repo-root .env (if present) under whatever is already in
    os.environ -- real environment variables always win."""
    values: dict[str, str] = {}
    if _ENV_PATH.is_file():
        for line in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"')
    values.update(os.environ)
    return values


_ENV = _load_dotenv_if_needed()


def _env(key: str) -> str | None:
    value = _ENV.get(key)
    if not value or value == "__TBD__":
        return None
    return value


@pytest.fixture(scope="session")
def pg_available() -> bool:
    host = _env("POSTGRES_HOST") or "localhost"
    port = _env("POSTGRES_PORT") or "5432"
    superuser_pw = _env("POSTGRES_PASSWORD")
    return bool(superuser_pw) and _can_connect(host, port, "postgres", superuser_pw, "postgres")


def _can_connect(host: str, port: str, user: str, password: str, dbname: str) -> bool:
    try:
        engine = sa.create_engine(
            f"postgresql+psycopg://{user}:{password}@{host}:{port}/{dbname}",
            pool_pre_ping=True,
        )
        with engine.connect() as conn:
            conn.execute(sa.text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:  # noqa: BLE001 -- connection failures vary by driver/OS; any of them means "skip"
        return False


@pytest.fixture(scope="session")
def pg_dsn_parts() -> dict[str, str]:
    """Raise (via pytest.skip) if the environment cannot support these tests."""
    host = _env("POSTGRES_HOST") or "localhost"
    port = _env("POSTGRES_PORT") or "5432"
    db = _env("POSTGRES_DB") or "retention"
    superuser_pw = _env("POSTGRES_PASSWORD")
    worker_pw = _env("APP_WORKER_DB_PASSWORD")
    console_pw = _env("APP_CONSOLE_DB_PASSWORD")

    if not (superuser_pw and worker_pw and console_pw):
        pytest.skip(
            "Postgres credentials not available (POSTGRES_PASSWORD / "
            "APP_WORKER_DB_PASSWORD / APP_CONSOLE_DB_PASSWORD) -- run "
            "`docker compose up -d postgres` and `alembic upgrade head` "
            "as documented in tests/invariants/README.md"
        )
    if not _can_connect(host, port, "postgres", superuser_pw, db):
        pytest.skip(f"cannot reach Postgres at {host}:{port} -- is `docker compose up -d postgres` running?")

    return {
        "host": host, "port": port, "db": db,
        "superuser_pw": superuser_pw, "worker_pw": worker_pw, "console_pw": console_pw,
    }


def _dsn(parts: dict[str, str], user: str, password: str) -> str:
    return f"postgresql+psycopg://{user}:{password}@{parts['host']}:{parts['port']}/{parts['db']}"


@pytest.fixture
def superuser_engine(pg_dsn_parts: dict[str, str]):
    engine = sa.create_engine(_dsn(pg_dsn_parts, "postgres", pg_dsn_parts["superuser_pw"]))
    yield engine
    engine.dispose()


@pytest.fixture
def worker_engine(pg_dsn_parts: dict[str, str]):
    engine = sa.create_engine(_dsn(pg_dsn_parts, "app_worker", pg_dsn_parts["worker_pw"]))
    yield engine
    engine.dispose()


@pytest.fixture
def console_engine(pg_dsn_parts: dict[str, str]):
    engine = sa.create_engine(_dsn(pg_dsn_parts, "app_console", pg_dsn_parts["console_pw"]))
    yield engine
    engine.dispose()
