"""Shared test fixtures. No live database is required for this test suite --
these tests cover request validation, auth logic, error shape, and rate
limiting, none of which need a real Postgres connection. Full integration
coverage (idempotent insert, RLS, approve/reject against real rows) belongs
in tests/invariants/, which already documents needing `docker compose up
postgres`.
"""
import os

import pytest

# Required settings the app fails loudly without (Settings has no defaults
# for these on purpose -- see api/settings.py). The DSN points at a real
# host:port shape but nothing here actually connects unless a test opens a
# session explicitly.
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://app_console:x@localhost:5432/retention_test")
os.environ.setdefault("API_KEY_HASH_PEPPER", "test-pepper")
os.environ.setdefault("CONSOLE_SESSION_SECRET", "test-console-secret")
os.environ.setdefault("CONSOLE_DEMO_REVIEWERS", "ops_reviewer_1,ops_reviewer_2")


@pytest.fixture
def client():
    from starlette.testclient import TestClient

    from api.main import create_app

    return TestClient(create_app())
