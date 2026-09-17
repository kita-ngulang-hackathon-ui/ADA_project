"""0010 worker update users

Revision ID: 0010_worker_update_users
Revises: 0009_worker_select_config
Create Date: 2026-09-17

Bugfix: migration 0006 granted app_worker INSERT on `users` but no UPDATE at
all, so `persistence.repositories.users.upsert_attributes`'s
`ON CONFLICT ... DO UPDATE` (needed every time INGEST sees an
already-known user_pseudonym again) fails with permission denied. Caught by
services/worker/tests/test_postgres_store.py.

Column-scoped, matching the security posture already used elsewhere
(e.g. recommendations' column-level grants): app_worker may keep
last_event_at/region_code/cohort_key current, but not touch
first_seen_at or lifecycle_state (an operator/console concern).
"""
from alembic import op

revision = "0010_worker_update_users"
down_revision = "0009_worker_select_config"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("GRANT UPDATE (last_event_at, region_code, cohort_key) ON users TO app_worker")


def downgrade() -> None:
    op.execute("REVOKE UPDATE (last_event_at, region_code, cohort_key) ON users FROM app_worker")
