"""Alembic environment.

Reads DATABASE_URL from the environment (never from alembic.ini, so the
same migration set applies unchanged across local/ci/demo). Runs migrations
as whatever role DATABASE_URL authenticates as -- in practice the Postgres
superuser, since 0001 creates the app_worker/app_console/app_readonly roles
that everything else depends on.
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
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Migrations never guess a connection string; "
            "copy .env.example to .env and fill it in."
        )
    return url


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
