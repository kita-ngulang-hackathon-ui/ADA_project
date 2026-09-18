"""0009 worker select tenant config

Revision ID: 0009_worker_select_config
Revises: 0008_feature_snapshots
Create Date: 2026-09-17

Bugfix: migration 0006 granted app_worker SELECT/INSERT on the event and
scoring tables but never on `tenants`, `event_type_mappings`, or
`incentives` -- only app_console got those. Every pipeline run needs all
three: `get_tenant()` reads `tenants` (profile_type) and
`event_type_mappings` (to build the ingest-mapping config), and
`load_incentives()` reads `incentives`. Without this grant the worker cannot
even start a run in production. Caught by
services/worker/tests/test_postgres_store.py exercising the real Postgres
role, the same way migration 0007 was caught by the invariant tests.

Read-only for app_worker: onboarding a tenant or editing its mapping/catalog
is a console-side (app_console) action, never a worker one.
"""
from alembic import op

revision = "0009_worker_select_config"
down_revision = "0008_feature_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT SELECT ON tenants, event_type_mappings, incentives TO app_worker")


def downgrade() -> None:
    op.execute("REVOKE SELECT ON tenants, event_type_mappings, incentives FROM app_worker")
