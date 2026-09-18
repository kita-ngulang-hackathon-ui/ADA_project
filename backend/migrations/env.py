"""Alembic environment.

Runs migrations as the Postgres superuser, built from POSTGRES_USER/
POSTGRES_PASSWORD/POSTGRES_HOST/POSTGRES_PORT/POSTGRES_DB -- never from
DATABASE_URL, which authenticates as app_console. Migration 0001 CREATEs
the app_worker/app_console/app_readonly roles, so nothing can migrate as
app_console on a fresh database; it doesn't exist yet. An explicit
MIGRATE_DATABASE_URL overrides this construction if set, for anyone who
wants a different migration-time role (e.g. a managed Postgres where the
"superuser" concept doesn't apply).
"""
import os
import sys
from logging.config import fileConfig
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool

# Make `persistence` importable when alembic is invoked from the repo root
# (`uv run alembic -c migrations/alembic.ini upgrade head`).
_PERSISTENCE_SRC = Path(__file__).resolve().parent.parent / "packages" / "persistence" / "src"
if str(_PERSISTENCE_SRC) not in sys.path:
    sys.path.insert(0, str(_PERSISTENCE_SRC))
_CORE_CONTRACTS_SRC = Path(__file__).resolve().parent.parent / "packages" / "core-contracts" / "src"
if str(_CORE_CONTRACTS_SRC) not in sys.path:
    sys.path.insert(0, str(_CORE_CONTRACTS_SRC))

from persistence.models import Base  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _database_url() -> str:
    override = os.environ.get("MIGRATE_DATABASE_URL")
    if override:
        return override

    host = os.environ.get("POSTGRES_HOST")
    port = os.environ.get("POSTGRES_PORT")
    db = os.environ.get("POSTGRES_DB")
    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    missing = [
        name
        for name, value in (
            ("POSTGRES_HOST", host), ("POSTGRES_PORT", port), ("POSTGRES_DB", db),
            ("POSTGRES_USER", user), ("POSTGRES_PASSWORD", password),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"Cannot build a migration connection string; missing {missing}. "
            "Migrations never guess a connection string; copy .env.example to "
            ".env and fill it in (or set MIGRATE_DATABASE_URL directly)."
        )
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{db}"


def run_migrations_offline() -> None:
    """Emit SQL to stdout instead of executing against a live database
    (`alembic upgrade head --sql`)."""
    context.configure(
        url=_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section) or {}
    configuration["sqlalchemy.url"] = _database_url()
    connectable = engine_from_config(configuration, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
